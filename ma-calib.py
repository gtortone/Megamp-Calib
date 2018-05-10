#!/usr/bin/env python3

# SYSTEM
import os.path as op
from sys import exit
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
from libs.megampset import MegampSet

# FLASK
from flask import Flask, request, flash, redirect, url_for, render_template
from flask_bootstrap import Bootstrap
from flask_nav import Nav
from flask_nav.elements import Navbar, View

# EPICS
from epics import PV

nav = Nav()

@nav.navigation()
def mynavbar():
    return Navbar(
        'Exotic Megamp Calibration',
        View('Monitoring', 'monitoring'),
    )

# global vars
app = Flask(__name__)

Bootstrap(app)
nav.init_app(app)

app.config['SECRET_KEY'] = hexlify(urandom(24))
app.config['BOOTSTRAP_SERVE_LOCAL'] = True
pvdb = {}			    # PV local cache

# callbacks
def onChangesPV(pvname=None, value=None, char_value=None, **kw):
    pvdb[pvname] = value

# MAIN

@app.route('/')
@app.route('/monitoring')
def monitoring():
    ms.refresh()
    if not ms.getModlist():
        flash('Megamp EPICS IOC not running or modules not detected - please verify IOC configuration', 'danger')
    # elif tq.getStatus() == 1:
    #	flash('Megamp Calibration monitoring page not available - please STOP calibration queue', 'danger')
    return render_template('monitoring.html', rcs=0, modlist=ms.getModlist(), ipaddress=netip, port=options.port)

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
    if not hasattr(mareport, "init"):
        mareport.init = True
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
            pv.value = 0  # enable CFD threshold (value 0 = true)

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

    jsobj["CH_CFD_THRESHOLD"] = pvdb[get_pvname(
        mareport.module, mareport.channel, 'CFDThreshold')]

    return(json.dumps(jsobj))

@app.route('/ma/plot/data')
def hdata():
    jsobj = {}
    jsobj["MA_ERROR"] = ""
    if options.sim is None:
        try:
            cy.writemem(2, 1)	 # generate histogram
        except Exception as e:
            jsobj["MA_ERROR"] = "USB write error (generate histogram)"
            return(json.dumps(jsobj))

        try:
            hist, gated_time, phys_time, num_events = cy.readhist()
        except Exception as e:
            jsobj["MA_ERROR"] = "USB write error (read histogram)"
            return(json.dumps(jsobj))
    else:
        hist = range(200)
        gated_time = phys_time = num_events = 0

    jsobj["H_TITLE"] = 'Megamp Module #{} - Channel #{}'.format(
        ms.getModule(), ms.getChannel())
    jsobj["H_VALUES"] = []
    for item in hist:
        jsobj["H_VALUES"].append(item)

    jsobj["H_GTIME"] = int(gated_time)
    jsobj["H_PTIME"] = int(phys_time)
    if(int(phys_time) > 0):
        jsobj["H_DTIME"] = round(
            ((int(phys_time) - int(gated_time)) / int(phys_time)) * 100, 2)
    else:
        jsobj["H_DTIME"] = "-"
    jsobj["H_EVENTS"] = num_events

    return(json.dumps(jsobj))

@app.route('/ma/plot/reset')
def hreset():
    jsobj = {}
    jsobj["MA_ERROR"] = ""
    if options.sim is None:
        try:
            cy.writemem(1, 1)  # reset current histogram
        except Exception as e:
            jsobj["MA_ERROR"] = "USB write error (reset histogram)"
    return json.dumps(jsobj)

@app.route('/ma/plot/setup', methods=['GET', 'POST'])
def hsetup():
    jsobj = {}
    jsobj["MA_ERROR"] = ""
    if options.sim is None:
        try:
            regvalue = cy.readmem(0)
        except Exception as e:
            jsobj["MA_ERROR"] = "USB write error (setup histogram)"
            return json.dumps(jsobj)
        if request.method == 'POST':    # write register
            # H_SWITCH
            hswitch = request.form.get("H_SWITCH")
            if hswitch is not None:
                try:
                    hswitch = int(hswitch)
                except Exception as e:
                    jsobj["MA_ERROR"] = "H_SWITCH wrong format error"
                    return json.dumps(jsobj)
                else:
                    if(hswitch == 0):
                        regvalue = regvalue & ~(1)
                    elif(hswitch == 1):
                        regvalue = regvalue | (1)
            # H_FILTER
            hfilter = request.form.get("H_FILTER")
            if hfilter is not None:
                try:
                    hfilter = int(hfilter)
                except Exception as e:
                    jsobj["MA_ERROR"] = "H_FILTER wrong format error"
                    return json.dumps(jsobj)
                else:
                    if(hfilter == 1):
                        regvalue = regvalue & ~(1 << 1)
                    else:
                        regvalue = regvalue | (1 << 1)
            # H_INPUT
            hinput = request.form.get("H_INPUT")
            if hinput is not None:
                try:
                    hinput = int(hinput)
                except Exception as e:
                    jsobj["MA_ERROR"] = "H_INPUT wrong format error"
                    return json.dumps(jsobj)
                else:
                    if(hinput == 0):
                        regvalue = regvalue & ~(1 << 2)
                    else:
                        regvalue = regvalue | (1 << 2)
            try:
                cy.writemem(0, regvalue)
            except Exception as e:
                jsobj["MA_ERROR"] = "USB write error (setup histogram)"
        elif request.method == 'GET':       # read register
            jsobj["H_SWITCH"] = regvalue 

    return json.dumps(jsobj)

@app.route('/ma/writepv', methods=['GET', 'POST'])
def writepv():
    jsobj = {}
    jsobj["MA_ERROR"] = ""
    pvname = request.form.get("PV_NAME")
    pvvalue = request.form.get("PV_VALUE")
    if((pvname is None) or (pvvalue is None)):
        jsobj["MA_ERROR"] = "PV write error (parameter missing)"
        return json.dumps(jsobj)

    pv = PV(pvname)
    if pv.wait_for_connection(timeout=2) == False:
        jsobj["MA_ERROR"] = "PV write error (PV not found)"
        return(json.dumps(jsobj))
    else:
        pv.value = pvvalue

    return json.dumps(jsobj)

def get_pvname(module, channel, attribute):
    pvname = 'MEGAMP:M' + str(module) + ':C' + \
        str(channel) + ':' + str(attribute)
    return(pvname)

def terminate(signum, frame):
    print("I: got termination signal... goodbye !")
    cleanup()

def cleanup():
    print("I: start cleanup")
    # tq.setStatus(3)
    exit(1)

class MAOptionParser(OptionParser):
    def exit(self, status=0, msg=None):
        if msg:
            print(msg)
        cleanup()


# create Megamp set
ms = MegampSet()

parser = MAOptionParser()
parser.add_option("-d", "--dev", action="store", type="string",
                  dest="netdev", default="eth0", help="network interface (default: eth0)")
parser.add_option("-p", "--port", action="store", type="int",
                  dest="port", default=5000, help="HTTP port (default: 5000)")
parser.add_option("-s", "--sim", action="store_true", dest="sim",
                  help="start in simulation mode (without USB)")
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
