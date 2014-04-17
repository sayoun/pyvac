# -*- coding: utf-8 -*-
import sys
import yaml

from datetime import datetime
import logging

from dateutil.relativedelta import relativedelta
from celery.task import Task, subtask

from pyvac.models import DBSession, Request
from pyvac.helpers.calendar import addToCal
from pyvac.helpers.mail import SmtpCache

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
        self.smtp = SmtpCache()
        self.log.info('using session %r, %r' % (self.session, id(self.session)))

        req = kwargs.get('data')
        self.log.info('RECEIVED %r' % req)

        self.process(req)

        return True

    def send_mail(self, sender, target, request, content):
        """ Send a mail """
        self.smtp.send_mail(sender, target, request, content)

    def get_admin_mail(self, admin):
        """ Return admin email from ldap dict or model """
        if isinstance(admin, dict):
            return admin['email']
        else:
            return admin.email


class WorkerPending(BaseWorker):

    name = 'worker_pending'

    def process(self, data):
        """ submitted by user
        send mail to manager
        """
        req = Request.by_id(self.session, data['req_id'])
        # send mail to manager
        src = req.user.email
        dst = req.user.manager_mail
        content = """New request from %s
Request details: %s""" % (req.user.name, req.summarymail)
        try:
            self.send_mail(sender=src, target=dst, request=req, content=content)
            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        self.session.flush()
        self.session.commit()


class WorkerAccepted(BaseWorker):

    name = 'worker_accepted'

    def process(self, data):
        """ accepted by manager
        send mail to user
        send mail to HR
        """
        req = Request.by_id(self.session, data['req_id'])
        # send mail to user
        src = req.user.manager_mail
        dst = req.user.email
        content = """Your request has been accepted by %s. Waiting for HR validation.
Request details: %s""" % (req.user.manager_name, req.summarymail)
        try:
            self.send_mail(sender=src, target=dst, request=req, content=content)

            # send mail to HR
            admin = req.user.get_admin(self.session)
            dst = self.get_admin_mail(admin)
            content = """Manager %s has accepted a new request. Waiting for your validation.
Request details: %s""" % (req.user.manager_name, req.summarymail)
            self.send_mail(sender=src, target=dst, request=req, content=content)

            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        self.session.flush()
        self.session.commit()


class WorkerAcceptedNotified(BaseWorker):

    name = 'worker_accepted_notified'

    def process(self, data):
        """ accepted by manager
        auto flag as accepted by HR
        """
        req = Request.by_id(self.session, data['req_id'])
        delta = (req.created_at + relativedelta(days=3)) - datetime.now()
        # after Request.created_at + 3 days, auto accept it by HR
        if delta.days > 3:
            # auto accept it as HR
            self.log.info('3 days passed, auto accept it by HR')

            # update request status after sending email
            req.update_status('APPROVED_ADMIN')
            self.session.flush()
            self.session.commit()

            data['autoaccept'] = True
            async_result = subtask(WorkerApproved).delay(data=data)
            self.log.info('task scheduled %r' % async_result)


class WorkerApproved(BaseWorker):

    name = 'worker_approved'

    def process(self, data):
        """ approved by HR
        send mail to user
        send mail to manager
        """
        req = Request.by_id(self.session, data['req_id'])

        admin = req.user.get_admin(self.session)
        # send mail to user
        src = self.get_admin_mail(admin)
        dst = req.user.email
        if 'autoaccept' in data:
            content = """Your request was automatically approved, it has been added to calendar.
Request details: %s""" % req.summarymail
        else:
            content = """HR has accepted your request, it has been added to calendar.
Request details: %s""" % req.summarymail
        try:
            self.send_mail(sender=src, target=dst, request=req, content=content)

            # send mail to manager
            src = self.get_admin_mail(admin)
            dst = req.user.manager_mail
            if 'autoaccept' in data:
                content = """A request you accepted was automatically approved, it has been added to calendar.
Request details: %s""" % req.summarymail
            else:
                content = """HR has approved a request you accepted, it has been added to calendar.
Request details: %s""" % req.summarymail
            self.send_mail(sender=src, target=dst, request=req, content=content)

            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        try:
            # add new entry in caldav
            addToCal(Conf.get('caldav').get('url'),
                     req.date_from,
                     req.date_to,
                     req.summarycal)
        except Exception as err:
            log.exception('Error while adding to calendar')
            req.flag_error(str(err))

        self.session.flush()
        self.session.commit()


class WorkerDenied(BaseWorker):

    name = 'worker_denied'

    def process(self, data):
        """ denied by XXX
        send mail to user
        """
        req = Request.by_id(self.session, data['req_id'])

        admin = req.user.get_admin(self.session)
        # send mail to user
        src = self.get_admin_mail(admin)
        dst = req.user.email
        content = """You request has been refused for the following reason: %s
Request details: %s""" % (req.reason, req.summarymail)
        try:
            self.send_mail(sender=src, target=dst, request=req, content=content)

            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        self.session.flush()
        self.session.commit()
