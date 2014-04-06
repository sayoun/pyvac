# -*- coding: utf-8 -*-
import sys
import yaml

from datetime import datetime
import logging

from dateutil.relativedelta import relativedelta
from celery.task import Task

from pyvac.models import DBSession, Request, User
from pyvac.helpers.calendar import addToCal
from pyvac.helpers.email import send_mail

try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

log = logging.getLogger(__name__)

with open(sys.argv[1]) as fdesc:
    Conf = yaml.load(fdesc, YAMLLoader)


class BaseWorker(Task):

    def process(self, data):
        raise NotImplementedError

    def run(self, *args, **kwargs):
        self.log = log
        self.session = DBSession()
        self.log.info('using session %r, %r' % (self.session, id(self.session)))

        req = kwargs.get('data')
        self.log.info('RECEIVED %r' % req)

        self.process(req)

        return True

    def send_mail(self, src, dst, req_type, text):

        send_mail(src, dst, req_type, text)


class WorkerPending(BaseWorker):

    name = 'worker_pending'

    def process(self, data):
        """ submitted by user
        send mail to manager
        send mail to HR
        """
        req = Request.by_id(self.session, data['req_id'])
        text = 'New request FROM %s (%s)' % (req.user.name,
                                             req.user.email)
        # send mail to manager
        src = req.user.email
        dst = req.user.manager_mail
        self.send_mail(src=src, dst=dst, req_type=req.status,
                       text=text)

        admins = User.get_admin_by_country(self.session, req.user.country)
        for admin in admins:
            # send mail to HR
            src = req.user.email
            dst = admin.email
            self.send_mail(src=src, dst=dst, req_type=req.status,
                           text=text)

        # update request status after sending email
        req.notified = True
        self.session.flush()
        self.session.commit()


class WorkerAccepted(BaseWorker):

    name = 'worker_accepted'

    def process(self, data):
        """ accepted by manager
        send mail to user
        """
        req = Request.by_id(self.session, data['req_id'])
        # after Request.created_at + 3 days, auto accept it by HR
        if (req.created_at + relativedelta(days=3)) >= datetime.now():
            # auto accept it as HR
            self.log.info('3 days passed, auto accept it by HR')

        text = 'FROM %s (%s) TO %s (%s)' % (req.user.manager.name,
                                            req.user.manager_mail,
                                            req.user.name,
                                            req.user.email)
        src = req.user.manager_mail
        dst = req.user.email
        self.send_mail(src=src, dst=dst, req_type=req.status,
                       text=text)

        # update request status after sending email
        req.notified = True
        self.session.flush()
        self.session.commit()


class WorkerAcceptedNotified(BaseWorker):

    name = 'worker_accepted_notified'

    def process(self, data):
        """ accepted by manager
        send mail to user
        """
        req = Request.by_id(self.session, data['req_id'])
        # after Request.created_at + 3 days, auto accept it by HR
        if (req.created_at + relativedelta(days=3)) >= datetime.now():
            # auto accept it as HR
            self.log.info('3 days passed, auto accept it by HR')

            # update request status after sending email
            req.update_status('APPROVED_ADMIN')
            self.session.flush()
            self.session.commit()


class WorkerApproved(BaseWorker):

    name = 'worker_approved'

    def process(self, data):
        """ approved by HR
        send mail to user
        send mail to manager
        """
        req = Request.by_id(self.session, data['req_id'])

        admins = User.get_admin_by_country(self.session, req.user.country)
        for admin in admins:
            # send mail to user
            src = admin.email
            dst = req.user.email
            text = 'FROM %s (%s) TO %s (%s)' % (admin.name,
                                                admin.email,
                                                req.user.name,
                                                req.user.email)
            self.send_mail(src=src, dst=dst, req_type=req.status,
                           text=text)
            # send mail to manager
            src = admin.email
            dst = req.user.manager_mail
            text = 'FROM %s (%s) TO %s (%s)' % (admin.name,
                                                admin.email,
                                                req.user.manager.name,
                                                req.user.manager_mail)
            self.send_mail(src=src, dst=dst, req_type=req.status,
                           text=text)

        # update request status after sending email
        req.notified = True
        self.session.flush()
        self.session.commit()

        # add new entry in caldav
        addToCal(Conf.get('caldav').get('url'),
                 req.date_from,
                 req.date_to,
                 req.summarycal)


class WorkerDenied(BaseWorker):

    name = 'worker_denied'

    def process(self, data):
        """ denied
        send mail to user
        """
        req = Request.by_id(self.session, data['req_id'])

        admins = User.get_admin_by_country(self.session, req.user.country)
        for admin in admins:
            # send mail to user
            src = admin.email
            dst = req.user.email
            text = 'DENIED FROM %s (%s) TO %s (%s)' % (admin.name,
                                                       admin.email,
                                                       req.user.name,
                                                       req.user.email)
            self.send_mail(src=src, dst=dst, req_type=req.status,
                           text=text)

        # update request status after sending email
        req.notified = True
        self.session.flush()
        self.session.commit()
