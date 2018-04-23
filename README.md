EXOTIC Megamp Calibration - Web panel
=====================================

Setup
-----

- install Python3 virtualenv packages

apt-get install dh-virtualenv

- create Python3 virtualenv

```
virtualenv -p python3 venv
```

- activate Python3 virtualenv

```
source venv/bin/activate
```

- install Flask and required packages

```
pip install pyusb
pip install flask 
pip install flask-admin
pip install flask-wtf
pip install WTForms
pip install pyepics
pip install flask-SQLalchemy
pip install SQLalchemy
```

- set PyEpics environment variable

export PYEPICS_LIBCA=/opt/epics/base/lib/linux-arm/libca.so

Run
---

- set environment variables

```
export FLASK_APP=ma-calib.py
```

- launch webapp

```
flask run --host=<IP_ADDRESS> --with-threads
or
python ma-calib.py
```

- use webapp

```
http://<IP_ADDRESS>:5000
```
