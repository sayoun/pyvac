# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = dict

from celery.task import Task, subtask

from pyvac.task.worker import WorkerTrialReminder
from pyvac.models import DBSession, User, Reminder as CoreReminder
from pyvac.helpers.ldap import LdapCache
from pyvac.helpers.conf import ConfCache


log = logging.getLogger(__name__)


class TrialReminderPoller(Task):

    name = 'trial_reminder_poller'

    def get_data(self, session, country):
        now = datetime.now()
        th_trial, th_good = self.trial_thresholds[country]

        ldap = LdapCache()
        arrivals = ldap.list_arrivals_country(country)

        matched = []
        for user_dn, dt in list(arrivals.items()):
            if not dt:
                continue

            dt_trial_threshold = dt + relativedelta(months=th_trial)
            dt_good = dt + relativedelta(months=th_good)
            if (now > dt_trial_threshold) and not (now > dt_good):
                matched.append((user_dn, dt))

        datas = []
        for user_dn, dt in matched:
            user = User.by_dn(session, user_dn)
            if not user:
                self.log.info('user not found: %s' % user_dn)
                continue
            if user.country not in self.countries:
                continue

            data = {'user_id': user.id}
            param = json.dumps(OrderedDict(data))
            rem = CoreReminder.by_type_param(session, 'trial_threshold', param)
            if not rem:
                data['duration'] = th_trial
                data['subject'] = self.subject
                datas.append(data)

        return datas

    def run(self, *args, **kwargs):
        self.log = log
        # init database connection
        session = DBSession()

        # init conf
        conf = ConfCache()
        remconf = conf.get('reminder', {}).get('trial_thresholds', {})
        self.countries = remconf.get('countries')
        self.trial_thresholds = remconf.get('values')
        self.subject = conf.get('reminder', {}).get('subject', 'Reminder')

        self.log.info('reminder conf: %s / %s' %
                      (self.countries, self.trial_thresholds))

        if not self.countries or not self.trial_thresholds:
            self.log.error('configuration is missing for trial reminder.')
            return False

        datas = [self.get_data(session, country)
                 for country in self.countries]

        # flatten the list
        datas = [item for sublist in datas for item in sublist]
        self.log.info('number of reminders to send: %d' % len(datas))

        for data in datas:
            async_result = subtask(WorkerTrialReminder).delay(data=data)
            self.log.info('task reminder scheduled %r' % async_result)

        return True
