#!/usr/bin/env python3

# SYSTEM
import os.path as op
from sys import exit
import threading
import time
from binascii import hexlify
from os import urandom
from random import random
import enum
import json
import logging
from optparse import OptionParser
import netifaces as ni
from signal import signal, SIGINT, SIGTERM, SIGHUP

# internal libs
from libs.cypress import Cypress, CypressError

# FLASK
from flask import Flask, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import flask_admin as admin
from flask_admin.contrib import sqla
from flask_admin.contrib.sqla import filters
from flask_admin.actions import action
from flask_admin.model.template import EndpointLinkRowAction, LinkRowAction
from sqlalchemy.event import listens_for
from sqlalchemy import event
from flask import request

# EPICS
from epics import PV

# global vars
app = Flask(__name__)

app.config['SECRET_KEY'] = hexlify(urandom(24))
app.config['DATABASE_FILE'] = 'tq_calib.sqlite'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
	 app.config['DATABASE_FILE']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
pvdb = {}			# PV local cache
fthread = None		# Flask thread

class task_status(enum.Enum):
		Pending = 1
		Running = 2
		Done = 3

class task_result(enum.Enum):
		Success = 1
		Failed = 2

class Task(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	module = db.Column(db.Integer, nullable=False)
	channel = db.Column(db.Integer, nullable=False)
	result = db.Column(db.Enum(task_result))
	status = db.Column(db.Enum(task_status))
	output = db.Column(db.Text)

class TaskView(sqla.ModelView):
	form_create_rules = ('module', 'channel')
	form_edit_rules = ('module', 'channel')
	form_excluded_columns = ('status', 'output', 'result')

	details_modal = True
	can_view_details = True
	can_edit = False
	column_list = ('module', 'channel', 'result', 'status')
	column_details_list = ('module', 'channel', 'output')

	from wtforms.validators import InputRequired, NumberRange
	form_args = dict(
		  module=dict(label='Megamp module', validators=[
						  InputRequired(), NumberRange(min=0, max=15)]),
		  channel=dict(label='Megamp channel', validators=[
							InputRequired(), NumberRange(min=0, max=15)])
	)

@listens_for(Task, 'before_insert')
def insert_handler(mapper, connection, target):
	target.status = task_status.Pending

class RunControl(admin.BaseView):

	@admin.expose('/', methods=['GET', 'POST'])
	def index(self):
		if request.method == 'GET':
			if request.values.get('cmd') == 'start':
				tq.setStatus(1)
			elif request.values.get('cmd') == 'stop':
				tq.setStatus(0)
		return self.render('runcontrol.html', rcs=tq.getStatus())

class Monitoring(admin.BaseView):

	@admin.expose('/', methods=['GET', 'POST'])
	def index(self):

		ms.refresh()
		if not ms.getModlist():
			flash('Megamp EPICS IOC not running or modules not detected - please verify IOC configuration', 'danger')
		elif tq.getStatus() == 1:
			flash('Megamp Calibration monitoring page not available - please STOP calibration queue', 'danger')

		return self.render('monitoring.html', rcs=tq.getStatus(), 
			modlist=ms.getModlist(), ipaddress=netip, port=options.port)

class TaskQueue():
	status = 0
	cthread = None

	def __init__(self):
		self.cthread = threading.Thread(target=self.run, args=(self,))
		self.cthread.start()

	def getStatus(self):
		return self.status

	def setStatus(self, s):
		self.status = s

	def getPendingTask(self):
		task = Task.query.filter_by(status=task_status.Pending).first()
		return task

	def run(self, tq):
		while True:
			if tq.getStatus() == 0:
				#print('I: thread sleep...')
				time.sleep(1)
			elif tq.getStatus() == 1:
				print("I: starting calibration tasks...")
				task = self.getPendingTask()
				if task != None:
					log = str()
					task.status = task_status.Running
					db.session.commit()
					
					time.sleep(5)
						
					print("TASK id = {}".format(task.id))
					print("TASK module = {}".format(task.module))
					print("TASK channel = {}".format(task.channel))

					for i in range(0,100):
						log += str(" bla ")
						
						task.output = log
						db.session.commit()
						
						task.result = task_result.Success
						db.session.commit()

						task.status = task_status.Done
						db.session.commit()
				time.sleep(1)
			if tq.getStatus() == 3:
				print("I: terminate calibration tasks...")
				break

class MegampSet():

	module = 0
	channel = 0
	modlist = []
	
	def __init__(self):
		print("I: init MegampSet")
		self.refresh()

	def refresh(self):
		pv = PV('MEGAMP:MOD:SEL', connection_timeout=2)
		self.modlist = pv.enum_strs

	def setModule(self, mod):
		if mod in self.modlist:
			self.module = mod
		else:
			raise IndexError
	
	def getModule(self):
		return self.module

	def setChannel(self, ch):
		if (int(ch) >= 0) and (int(ch) <= 15):
			self.channel = ch
		else:
			raise IndexError

	def getChannel(self):
		return self.channel

	def getModlist(self):
		return self.modlist

# MAIN

def onChangesPV(pvname=None, value=None, char_value=None, **kw):
	pvdb[pvname] = value

@app.route('/ma/out/<module>/<channel>')
def maout(module, channel):
	jsobj = {}
	jsobj["MA_ERROR"] = ""

	try:
		ms.setModule(module)
	except Exception as e:
		jsobj["MA_ERROR"] = "Megamp module not available"
		return(json.dumps(jsobj))
	
	try:
		ms.setChannel(channel)
	except Exception as e:
		jsobj["MA_ERROR"] = "Megamp channel out of range"
		return(json.dumps(jsobj))

	pvname = get_pvname(module, channel, 'OUT')
	pv = PV(pvname)
	if pv.wait_for_connection() == False:
		jsobj["MA_ERROR"] = "Megamp EPICS IOC error"
		return(json.dumps(jsobj))
	else:
		pv.value = 1

	return(json.dumps(jsobj))

@app.route('/ma/report')
def mareport():
	jsobj = {}
	jsobj["MA_ERROR"] = ""
	mareport.module = -1
	mareport.channel = -1
	mareport.pvcfdthr = 0

	if mareport.module != ms.getModule() or mareport.channel != ms.getChannel():
		pvname = get_pvname(ms.getModule(), ms.getChannel(), 'CFD')
		pv = PV(pvname)
		if pv.wait_for_connection(timeout=2) == False:
			jsobj["MA_ERROR"] = "Megamp EPICS IOC error"
			return(json.dumps(jsobj))
		else:
			pv.value = 0	# enable CFD threshold (disable = false)

		pvname = get_pvname(ms.getModule(), ms.getChannel(), 'CFDThreshold')
		mareport.pvcfdthr = PV(pvname)
		if mareport.pvcfdthr.wait_for_connection(timeout=2) == False:
			jsobj["MA_ERROR"] = "Megamp EPICS IOC error"
			return(json.dumps(jsobj))
		else:
			pvdb[pvname] = mareport.pvcfdthr.value
			mareport.pvcfdthr.add_callback(onChangesPV)

			mareport.module = ms.getModule()
			mareport.channel = ms.getChannel()

	jsobj["CH_CFD_THRESHOLD"] = pvdb[get_pvname(mareport.module, mareport.channel, 'CFDThreshold')]
	
	return(json.dumps(jsobj))

@app.route('/ma/plot/data')
def hdata():
	jsobj = {}
	jsobj["MA_ERROR"] = ""
	if options.sim is None:
		try:
			cy.writemem(0, 7)	 # enable histogram
		except Exception as e:
			jsobj["MA_ERROR"] = "USB write error (enable histogram)"
			return(json.dumps(jsobj))

		try:
			cy.writemem(2, 1)	 # generate histogram
		except Exception as e:
			jsobj["MA_ERROR"] = "USB write error (generate histogram)"
			return(json.dumps(jsobj))

		try:
			hist, dead_time, time_meas, num_event, idle_time = cy.readhist()
		except Exception as e:
			jsobj["MA_ERROR"] = "USB write error (read histogram)"
			return(json.dumps(jsobj))
	else:
		hist = range(200)
		dead_time = time_meas = num_event = idle_time = 0

	jsobj["H_TITLE"] = 'Megamp Module #{} - Channel #{}'.format(ms.getModule(),ms.getChannel())
	jsobj["H_VALUES"] = []
	for item in hist:
		jsobj["H_VALUES"].append(item)

	jsobj["H_DTIME"] = int(dead_time)
	jsobj["H_TIME"] = int(time_meas)
	jsobj["H_EVENTS"] = num_event
	jsobj["H_ITIME"] = int(idle_time)

	return(json.dumps(jsobj))

@app.route('/ma/plot/reset')
def hreset():
	jsobj = {}
	jsobj["MA_ERROR"] = ""
	if options.sim is None: 
		try:
			cy.writemem(1, 1)	# reset current histogram
		except Exception as e:
			jsobj["MA_ERROR"] = "USB write error (reset histogram)"
	return json.dumps(jsobj)

def get_pvname(module, channel, attribute):
	pvname = 'MEGAMP:M' + str(module) + ':C' + str(channel) + ':' + str(attribute)
	return(pvname)

def terminate(signum, frame):
	print("I: got termination signal... goodbye !")
	cleanup()

def cleanup():
	print("I: start cleanup")
	tq.setStatus(3)
	exit(1)

class MAOptionParser(OptionParser):
	def exit(self, status=0, msg=None):
		if msg:
			print(msg)
		cleanup()

admin = admin.Admin(app, url='/', name='EXOTIC Megamp Calibration', template_mode='bootstrap3')
admin.add_view(TaskView(Task, db.session, name='Tasks', url='/tasks'))
admin.add_view(RunControl(name="Queue Control", category='Calibration'))
admin.add_view(Monitoring(name="Monitoring", category='Calibration'))

# build an empty db, if one does not exist yet.
app_dir = op.realpath(op.dirname(__file__))
database_path = op.join(app_dir, app.config['DATABASE_FILE'])
if not op.exists(database_path):
	db.drop_all()
	db.create_all()
	db.session.commit()

# create task queue
tq = TaskQueue()
# create Megamp slot
ms = MegampSet()

parser = MAOptionParser()
parser.add_option("-d", "--dev", action="store", type="string", dest="netdev", default="eth0", help="network interface (default: eth0)")
parser.add_option("-p", "--port", action="store", type="int", dest="port", default=5000, help="HTTP port (default: 5000)")
parser.add_option("-s", "--sim", action="store_true", dest="sim", help="start in simulation mode (without USB)")
(options, args) = parser.parse_args()

try:
	netip = ni.ifaddresses(options.netdev)[ni.AF_INET][0]['addr']
except Exception as e:
	print("E: network interface error - {}".format(e))
	cleanup()

if options.sim == None:
	cy = Cypress()
	
	try:
		cy.open(0)
	except Exception as e:
		print("E: USB error opening device")
		print("E: {}".format(e))
		cleanup()

	try:
		cy.config()
	except Exception as e:
		print("E: USB error configuring device")
		print("E: {}".format(e))
		cleanup()

	try:
		cy.busclear()
	except Exception as e:
		print("E: USB error during bus clear")
		print("E: {}".format(e))
		cleanup()

# disable Flask console logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

print("-----------------------")
print("Exotic Calibration Tool")
print("-----------------------")
print("* network interface: {}".format(options.netdev))
print("* URL: http://{}:{}/".format(netip, options.port))
if options.sim:
	print("-- simulation mode without USB --")

if __name__ == "__main__":
	signal(SIGINT, terminate)
	signal(SIGTERM, terminate)
	signal(SIGHUP, terminate)

	try:
		app.run(host=netip, port=options.port, threaded=True)
	except Exception as e:
		print("E: {}".format(e))
		cleanup()
