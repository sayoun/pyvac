Pyvac README
============

Getting Started
---------------

>>> cd <directory containing this file>

Install package in venv
>>> $venv/bin/python setup.py develop

Initialize database
>>> $venv/bin/pyvac_install development.ini

Start the website
>>> $venv/bin/pserve development.ini

Start celery poller
>>> $venv/bin/pyvac_celeryd pyvac/conf/pyvac.yaml -l DEBUG -c 1 -B -Q pyvac_poll

Start celery worker
>>> $venv/bin/pyvac_celeryd pyvac/conf/pyvac.yaml -l DEBUG -c 1 -Q pyvac_work
