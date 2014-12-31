# -*- coding: utf-8 -*-
import sys
import yaml

from datetime import datetime
import logging
import transaction

from celery.task import Task, subtask

from pyvac.models import DBSession, Request, User
from pyvac.helpers.calendar import addToCal
from pyvac.helpers.mail import SmtpCache

try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

log = logging.getLogger(__name__)


class BaseWorker(Task):

    def process(self, data):
        raise NotImplementedError

    def run(self, *args, **kwargs):
        self.log = log
        self.session = DBSession()
        self.smtp = SmtpCache()
        self.log.info('using session %r, %r' %
                      (self.session, id(self.session)))

        req = kwargs.get('data')
        self.log.info('RECEIVED %r' % req)

        self.process(req)

        return True

    def send_mail(self, sender, target, request, content):
        """ Send a mail """
        subject = 'Request %s' % request.status
        self.smtp.send_mail(sender, target, subject, content)

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
        if 'reminder' in data:
            content = """A request from %s is still waiting your approval
Request details: %s""" % (req.user.name, req.summarymail)
        else:
            content = """New request from %s
Request details: %s""" % (req.user.name, req.summarymail)
        try:
            self.send_mail(sender=src, target=dst, request=req,
                           content=content)
            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        self.session.flush()
        transaction.commit()


class WorkerPendingNotified(BaseWorker):

    name = 'worker_pending_notified'

    def process(self, data):
        """ submitted by user

        re-send mail to manager if close to requested date_from
        """
        req = Request.by_id(self.session, data['req_id'])
        # after new field was added, it may not be set yet
        if not req.date_updated:
            return

        delta_deadline = req.date_from - req.date_updated
        if delta_deadline.days <= 2:
            if datetime.now().date() != req.date_updated.date():
                # resend the mail
                self.log.info('2 days left before requested date, '
                              'remind the manager')

                data['reminder'] = True
                async_result = subtask(WorkerPending).delay(data=data)
                self.log.info('task scheduled %r' % async_result)


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
            self.send_mail(sender=src, target=dst, request=req,
                           content=content)

            # send mail to HR
            admin = req.user.get_admin(self.session)
            dst = self.get_admin_mail(admin)
            content = """Manager %s has accepted a new request. Waiting for your validation.
Request details: %s""" % (req.user.manager_name, req.summarymail)
            self.send_mail(sender=src, target=dst, request=req,
                           content=content)

            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        self.session.flush()
        transaction.commit()


class WorkerAcceptedNotified(BaseWorker):

    name = 'worker_accepted_notified'

    def process(self, data):
        """ accepted by manager
        auto flag as accepted by HR
        """
        req = Request.by_id(self.session, data['req_id'])
        # after new field was added, it may not be set yet
        if not req.date_updated:
            return

        delta = datetime.now() - req.date_updated
        # after Request.date_updated + 3 days, auto accept it by HR
        if delta.days >= 3:
            # auto accept it as HR
            self.log.info('3 days passed, auto accept it by HR')

            # update request status after sending email
            req.update_status('APPROVED_ADMIN')
            self.session.flush()
            transaction.commit()

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
            self.send_mail(sender=src, target=dst, request=req,
                           content=content)

            # send mail to manager
            src = self.get_admin_mail(admin)
            dst = req.user.manager_mail
            if 'autoaccept' in data:
                content = """A request you accepted was automatically approved, it has been added to calendar.
Request details: %s""" % req.summarymail
            else:
                content = """HR has approved a request you accepted, it has been added to calendar.
Request details: %s""" % req.summarymail
            self.send_mail(sender=src, target=dst, request=req,
                           content=content)

            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        try:
            if 'caldav.url' in data:
                caldav_url = data['caldav.url']
            else:
                conf_file = sys.argv[1]
                with open(conf_file) as fdesc:
                    Conf = yaml.load(fdesc, YAMLLoader)
                caldav_url = Conf.get('caldav').get('url')

            # add new entry in caldav
            ics_url = addToCal(caldav_url,
                               req.date_from,
                               req.date_to,
                               req.summarycal)
            # save ics url in request
            req.ics_url = ics_url
        except Exception as err:
            log.exception('Error while adding to calendar')
            req.flag_error(str(err))

        self.session.flush()
        transaction.commit()


class WorkerDenied(BaseWorker):

    name = 'worker_denied'

    def process(self, data):
        """ denied by last_action_user_id
        send mail to user
        """
        req = Request.by_id(self.session, data['req_id'])

        # retrieve user who performed last action
        action_user = User.by_id(self.session, req.last_action_user_id)
        # send mail to user
        src = action_user.email
        dst = req.user.email
        content = """You request has been refused for the following reason: %s
Request details: %s""" % (req.reason, req.summarymail)
        try:
            self.send_mail(sender=src, target=dst, request=req,
                           content=content)

            # update request status after sending email
            req.notified = True
        except Exception as err:
            log.exception('Error while sending mail')
            req.flag_error(str(err))

        self.session.flush()
        transaction.commit()


class WorkerMail(BaseWorker):

    name = 'worker_mail'

    def process(self, data):
        """ simple worker task for sending a mail using internal helper """

        sender = data['sender']
        target = data['target']
        subject = data['subject']
        content = data['content']

        try:
            self.smtp.send_mail(sender, target, subject, content)
        except Exception:
            log.exception('Error while sending mail')
