# SYSTEM
import os.path as op
import threading, time
from binascii import hexlify
from os import urandom
from random import random
import enum
import json

# internal libs
from libs import cypress

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

# ROOT
# from ROOT import gROOT, TCanvas, TH1I, TString, TBufferJSON

# EPICS
from epics import PV

app = Flask(__name__)

app.config['SECRET_KEY'] = hexlify(urandom(24))
app.config['DATABASE_FILE'] = 'tq_calib.sqlite'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + app.config['DATABASE_FILE']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
pvdb = {}

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
   details_modal = True
   can_view_details = True
   can_edit = False
   column_list = ('module', 'channel', 'result', 'status')
   column_details_list = ('module', 'channel', 'output')

   from wtforms.validators import InputRequired, NumberRange
   form_args = dict(
        module=dict(label='Megamp module', validators=[InputRequired(), NumberRange(min=0, max=15)]),
        channel=dict(label='Megamp channel', validators=[InputRequired(), NumberRange(min=0, max=15)])
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
      pv = PV('MEGAMP:MOD:SEL', connection_timeout=2)
      _modlist = pv.enum_strs

      if not _modlist:
      	flash('Megamp EPICS IOC not running or modules not detected - please verify IOC configuration', 'danger')
      elif tq.getStatus() == 1:
      	flash('Megamp Calibration monitoring page not available - please STOP calibration queue', 'danger')

      return self.render('monitoring.html', rcs=tq.getStatus(), modlist=_modlist)

class TaskQueue():
   status = 0
   cthread = None

   def __init__(self):
      cthread = threading.Thread(target=self.run, args=(self,))
      cthread.start()

   def getStatus(self):
      return self.status

   def setStatus(self,s):
      self.status = s

   def getPendingTask(self):
      task = Task.query.filter_by(status=task_status.Pending).first()
      return task
   
   def run(self, tq):
      while True:
         if tq.getStatus() == 0:
            #print('<thread sleep...>')
            time.sleep(1)
         if tq.getStatus() == 1:
            print("Starting calibration tasks...")
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

# MAIN

def onChangesPV(pvname=None, value=None, char_value=None, **kw):
	pvdb[pvname] = value

@app.route('/hist/<module>/<channel>')
def hist(module, channel):
	if not hasattr(hist, "fChannel"):
		hist.fChannel = -1 
	if not hasattr(hist, "fModule"):
		hist.fModule = -1
	
	if module != hist.fModule or channel != hist.fChannel:
		pvname = get_pvname(module, channel, 'CFD')
		pv = PV(pvname, connection_timeout=2)
		pv.value = 0	# enable CFD threshold (disable = false)

		pvname = get_pvname(module, channel, 'CFDThreshold')
		hist.pvcfdthr = PV(pvname, connection_timeout=2)
		pvdb[pvname] = hist.pvcfdthr.value
		hist.pvcfdthr.add_callback(onChangesPV)

		hist.fModule = module
		hist.fChannel = channel

	title = 'Megamp Module #' + str(module) + " - Channel #" + str(channel)
	plot = TH1I('plot', title, 100, -4, 4)
	for i in range(25000):
		px = random() 
		plot.Fill(px)

	jsonhist = TBufferJSON.ConvertToJSON(plot)
	objarr = {}
	objarr["plot"] = json.loads(str(jsonhist))
	objarr["cfdthreshold"] = pvdb[get_pvname(module, channel, 'CFDThreshold')]

	return(json.dumps(objarr))

@app.route('/ma/<module>/<channel>')
def ma(module, channel):
	if not hasattr(ma, "fChannel"):
		ma.fChannel = -1 
	if not hasattr(ma, "fModule"):
		ma.fModule = -1

	if module != ma.fModule or channel != ma.fChannel:
		pvname = get_pvname(module, channel, 'CFD')
		pv = PV(pvname, connection_timeout=2)
		pv.value = 0	# enable CFD threshold (disable = false)

		pvname = get_pvname(module, channel, 'CFDThreshold')
		ma.pvcfdthr = PV(pvname, connection_timeout=2)
		pvdb[pvname] = ma.pvcfdthr.value
		ma.pvcfdthr.add_callback(onChangesPV)

		ma.fModule = module
		ma.fChannel = channel
	
	jsobj = {}
	jsobj["hvalues"] = []
	jsobj["htitle"] = 'Megamp Module #' + str(module) + " - Channel #" + str(channel)

	for _ in range(18000):
		jsobj["hvalues"].append(random()*4096)

	jsobj["cfdthreshold"] = pvdb[get_pvname(module, channel, 'CFDThreshold')]

	return(json.dumps(jsobj))

def get_pvname(module, channel, attribute):
	pvname = 'MEGAMP:M' + str(module) + ':C' + str(channel) + ':' + str(attribute)
	return(pvname)

admin = admin.Admin(app, url='/', name='EXOTIC Megamp Calibration', template_mode='bootstrap3')
admin.add_view(TaskView(Task, db.session, name='Tasks', url='/tasks'))
admin.add_view(RunControl(name="Queue Control", category='Calibration'))
admin.add_view(Monitoring(name="Monitoring", category='Calibration'))

# Build an empty db, if one does not exist yet.
app_dir = op.realpath(op.dirname(__file__))
database_path = op.join(app_dir, app.config['DATABASE_FILE'])
if not op.exists(database_path):
   db.drop_all()
   db.create_all()
   db.session.commit()

tq = TaskQueue()

if __name__ == "__main__":
   app.run()
