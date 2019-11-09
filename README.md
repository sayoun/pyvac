Pyvac
=====

Pyvac's purpose is to allow Human Resources (HR) to handle an employee leave calendar and manage internal employee ldap.

It's a full web application written in Python, using Pyramid as HTTP framework and Celery as backend framework.

Workflow
--------

A leave request requires double validation (both by the user's manager and by the HR administrator) to be fully processed and validated.
Either a manager or HR admin can deny a request but must provide a reason.
After HR validation, the request will be automatically added to the caldav calendar.

Each step in the workflow generates a notification email to affected parties.

### Request a new leave as a normal user:

- log in/open the application
- select desired period on the calendar, by clicking on start and end date
- select type of leave: **CP** (*Congés Payés*, paid time off) or **RTT** (*Réduction du Temps de Travail*, unpaid time off)
- select AM/PM if needed (only enabled when requesting a single date)
- click submit

-> an email is sent to the user's manager to notify them of a new pending request

### Handling a leave request as a manager

- log in/open the application
- go to request list page
- check for conflicting user requests due to overlapping time-off requests
- click on accept or deny button, provide a reason if denied

-> an email is sent to the user to notify them of their manager's validation
-> an email is sent to the HR admin to notify them of a new pending request that has been validated by a manager

### Handling a leave request as HR admin

- log in/open the application
- go to request list page
- check for conflicting user requests due to overlapping time-off requests
- click on accept or deny button, provide a reason if denied

-> an email is sent to the user to notify them of HR's validation
-> an email is sent to the manager to notify them of HR's validation
-> a new entry is added to caldav for this leave request


Requirements
------------

You will need at least a python 3.5 and a Redis server (for Celery backend).

Getting Started
---------------

    cd <directory containing this file>

Install requirements and package in venv. Cryptacular will generate a scons error if not installed before setup.py.

    pip install cryptacular
    python setup.py develop

Initialize database (sqlite by default)

    pyvac_install development.ini

Optional: Import ldap users if using ldap

    pyvac_import development.ini

Start the website

    pserve development.ini

Start celery worker process

    pyvac_celeryd conf/pyvac.yaml -l DEBUG -c 1 -Q pyvac_work

Start celery poller process

    pyvac_celeryd conf/pyvac.yaml -l DEBUG -c 1 -B -Q pyvac_poll

### Finally, to be ready to use:

- log in using admin account (default credentials: admin/changeme)
- go to profile page and change password and email
- create a manager and some users


Use postgresql instead of sqlite
--------------------------------

You need to first create a database for pyvac to work

    sudo -u postgres psql
    postgres=# create database pyvac;
    postgres=# create user pyvac with encrypted password 'pyvac';
    postgres=# grant all privileges on database pyvac to pyvac;

Then you need to update configuration files to use this. You need to uncomment line `sqlalchemy.url` to enable postgresql usage.

* update `development.ini` file to frontend
* update `pyvac.yaml` file for backend

Then initialize database again

    pyvac_install development.ini
