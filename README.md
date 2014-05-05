Pyvac
=====

Pyvac purpose is to allow Human Resources (HR) to handle leave calendar of employee and manage internal ldap of employee.

It's a full web application written in Python, using Pyramid as HTTP framework and Celery as backend framework.

Workflow
--------

A leave request needs a double validation, one by user manager and one by HR administrator, to be fully processed and valid.
Both manager and HR admin can deny a request but must provide a reason.
After HR validation, the request will be automatically added to the caldav calendar.

Each step in the workflow is notified by email to whom his concerned.

### Request a new leave as a simple user:

- login/open the application
- select desired period on the calendar, by clicking on starting and ending date
- select type of leave CP or RTT
- click submit

-> an email is send to the user manager to notify him of a new pending request

### Handling a leave request as a manager

- login/open the application
- go to request list page
- check if there is a conflict between user requests for some overlapping periods
- click on accept or deny button, provide a reason if denied

-> an email is send to the user to notify him of his manager validation
-> an email is send to the HR admin to notify him of a new pending request validated by a manager

### Handling a leave request as HR admin

- login/open the application
- go to request list page
- check if there is a conflict between user requests for some overlapping periods
- click on accept or deny button, provide a reason if denied

-> an email is send to the user to notify him of HR validation
-> an email is send to the manager to notify him of HR validation
-> a new entry is added to caldav for this leave request


Getting Started
---------------

    cd <directory containing this file>

Install package in venv

    $venv/bin/python setup.py develop

Initialize database

    $venv/bin/pyvac_install development.ini

Optionnal: Import ldap users if using ldap

    $venv/bin/pyvac_import development.ini

Start the website

    $venv/bin/pserve development.ini

Start celery worker process

    $venv/bin/pyvac_celeryd pyvac/conf/pyvac.yaml -l DEBUG -c 1 -Q pyvac_work

Start celery poller process

    $venv/bin/pyvac_celeryd pyvac/conf/pyvac.yaml -l DEBUG -c 1 -B -Q pyvac_poll

### Finally to be ready to use:

- log in using admin account (admin/changeme)
- go to profile page and change password and email
- create user/managers

