# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

from .base import View

from pyramid.httpexceptions import HTTPFound
from pyramid.url import route_url

from pyvac.models import Request, VacationType
# from pyvac.helpers.i18n import trans as _
from pyvac.helpers.calendar import delFromCal

import yaml
try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

log = logging.getLogger(__name__)


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days + 1)):
        yield start_date + timedelta(n)


class Send(View):

    def render(self):
        try:
            form_date_from = self.request.params.get('date_from')
            if ' - ' not in form_date_from:
                msg = 'Invalid format for period.'
                self.request.session.flash('error;%s' % msg)
                return HTTPFound(location=route_url('home', self.request))

            dates = self.request.params.get('date_from').split(' - ')
            date_from = datetime.strptime(dates[0], '%d/%m/%Y')
            date_to = datetime.strptime(dates[1], '%d/%m/%Y')

            days = float(len([d for d in daterange(date_from, date_to)
                              if d.isoweekday() not in [6, 7]]))

            days_diff = (date_to - date_from).days
            if days_diff < 0:
                msg = 'Invalid format for period.'
                self.request.session.flash('error;%s' % msg)
                return HTTPFound(location=route_url('home', self.request))

            if (date_to == date_from) and days > 1:
                # same day, asking only for one or less day duration
                msg = 'Invalid value for days.'
                self.request.session.flash('error;%s' % msg)
                return HTTPFound(location=route_url('home', self.request))

            if days <= 0:
                msg = 'Invalid value for days.'
                self.request.session.flash('error;%s' % msg)
                return HTTPFound(location=route_url('home', self.request))

            vac_type = VacationType.by_id(self.session,
                                          int(self.request.params.get('type')))

            # label field is used when requesting half day
            label = u''
            breakdown = self.request.params.get('breakdown')
            if breakdown != 'FULL':
                # handle half day
                if (days > 1):
                    msg = 'AM/PM option must be used only when requesting a single day.'
                    self.request.session.flash('error;%s' % msg)
                    return HTTPFound(location=route_url('home', self.request))
                else:
                    days = 0.5
                    label = unicode(breakdown)

            request = Request(date_from=date_from,
                              date_to=date_to,
                              days=days,
                              vacation_type=vac_type,
                              status=u'PENDING',
                              user=self.user,
                              notified=False,
                              label=label,
                              )
            self.session.add(request)
            self.session.flush()

            if request:
                msg = 'Request sent to your manager.'
                self.request.session.flash('info;%s' % msg)
                # call celery task directly, do not wait for polling
                from celery.registry import tasks
                from celery.task import subtask
                req_task = tasks['worker_pending']
                data = {'req_id': request.id}
                subtask(req_task).delay(data=data)

        except Exception as exc:
            log.error(exc)
            msg = ('An error has occured while processing this request: %r'
                   % exc)
            self.request.session.flash('error;%s' % msg)

        return HTTPFound(location=route_url('home', self.request))


class List(View):
    """
    List all user requests
    """
    def render(self):

        req_list = {'requests': [], 'conflicts': {}}
        requests = []
        if self.user.is_admin:
            country = self.user.country
            requests = Request.all_for_admin_per_country(self.session,
                                                         country)
            # check if admin user is also a manager, in this case merge all
            # requests
            requests_manager = Request.by_manager(self.session, self.user)
            # avoid duplicate entries
            req_to_add = [req for req in requests_manager
                          if req not in requests]
            requests.extend(req_to_add)
        elif self.user.is_super:
            requests = Request.by_manager(self.session, self.user)

        if requests:
            conflicts = {}
            for req in requests:
                req.conflict = [req2.summary for req2 in
                                Request.in_conflict(self.session, req)]
                if req.conflict:
                    conflicts[req.id] = '\n'.join(req.conflict)
            req_list['requests'] = requests
            req_list['conflicts'] = conflicts

        # always add our requests
        for req in Request.by_user(self.session, self.user):
            if req not in req_list['requests']:
                req_list['requests'].append(req)

        return req_list


class Accept(View):
    """
    Accept a request
    """

    def render(self):

        req_id = self.request.params.get('request_id')
        req = Request.by_id(self.session, req_id)
        if not req:
            return ''

        data = {'req_id': req.id}

        only_manager = False
        # we should handle the case where the admin is also a user manager
        if (self.user.ldap_user and (req.user.manager_dn == self.user.dn)
                and (req.status == 'PENDING')):
            only_manager = True

        if self.user.is_admin and not only_manager:
            req.update_status('APPROVED_ADMIN')
            # save who performed this action
            req.last_action_user_id = self.user.id

            task_name = 'worker_approved'
            settings = self.request.registry.settings
            with open(settings['pyvac.celery.yaml']) as fdesc:
                Conf = yaml.load(fdesc, YAMLLoader)
            data['caldav.url'] = Conf.get('caldav').get('url')
        else:
            req.update_status('ACCEPTED_MANAGER')
            # save who performed this action
            req.last_action_user_id = self.user.id
            task_name = 'worker_accepted'

        self.session.flush()

        # call celery task directly, do not wait for polling
        from celery.registry import tasks
        from celery.task import subtask
        req_task = tasks[task_name]

        subtask(req_task).delay(data=data)

        return req.status


class Refuse(View):
    """
    Refuse a request
    """

    def render(self):

        req_id = self.request.params.get('request_id')
        req = Request.by_id(self.session, req_id)
        if not req:
            return ''
        reason = self.request.params.get('reason')

        req.reason = reason
        req.update_status('DENIED')
        # save who performed this action
        req.last_action_user_id = self.user.id
        self.session.flush()

        # call celery task directly, do not wait for polling
        from celery.registry import tasks
        from celery.task import subtask
        req_task = tasks['worker_denied']
        data = {'req_id': req.id}
        subtask(req_task).delay(data=data)

        return req.status


class Cancel(View):
    """
    Cancel a request and remove entry from calendar if needed.
    """

    def render(self):

        req_id = self.request.params.get('request_id')
        req = Request.by_id(self.session, req_id)
        if not req:
            return ''

        # delete from calendar
        if req.status == 'APPROVED_ADMIN' and req.ics_url:
            settings = self.request.registry.settings
            with open(settings['pyvac.celery.yaml']) as fdesc:
                Conf = yaml.load(fdesc, YAMLLoader)
            caldav_url = Conf.get('caldav').get('url')
            delFromCal(caldav_url, req.ics_url)

        req.update_status('CANCELED')
        # save who performed this action
        req.last_action_user_id = self.user.id

        self.session.flush()
        return req.status


class Export(View):
    """
    Display form to export requests
    """
    def render(self):
        import calendar
        from datetime import datetime
        months = calendar.month_name
        return {'months': months[1:], 'current_month': datetime.now().month}


class Exported(View):
    """
    Export all requests of a month to csv
    """
    def render(self):

        exported = {}
        if self.user.is_admin:
            country = self.user.country
            month = int(self.request.params.get('month'))
            requests = Request.get_by_month(self.session, country, month=month)
            data = []
            header = '%s,%s,%s,%s,%s,%s,%s' % ('#', 'lastname', 'firstname',
                                               'from', 'to', 'number', 'type')
            data.append(header)
            for idx, req in enumerate(requests, start=1):
                data.append('%d,%s' % (idx, req.summarycsv))
            exported = '\n'.join(data)
        return {u'exported': exported}
