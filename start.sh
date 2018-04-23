#!/bin/bash

source venv/bin/activate
export FLASK_APP=ma-calib.py
flask run --host=`/sbin/ifconfig eth0 | grep "inet addr" | cut -d ':' -f 2 | cut -d ' ' -f 1`
