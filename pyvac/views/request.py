# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from .base import View

from pyramid.httpexceptions import HTTPFound
from pyramid.url import route_url

from pyvac.models import Request
# from pyvac.helpers.i18n import trans as _

log = logging.getLogger(__name__)


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
            days = int(self.request.params.get('days'))
            type = self.request.params.get('type')

            if days <= 0:
                msg = 'Invalid value for days.'
                self.request.session.flash('error;%s' % msg)
                return HTTPFound(location=route_url('home', self.request))

            request = Request(date_from=date_from,
                              date_to=date_to,
                              days=days,
                              type=type,
                              status=u'PENDING',
                              user=self.user,
                              notified=False,
                              )
            self.session.add(request)
            self.session.flush()

            if request:
                msg = 'Request sent to your manager.'
                self.request.session.flash('info;%s' % msg)
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
            requests = Request.all_for_admin(self.session)
        elif self.user.is_super:
            requests = Request.by_manager(self.session, self.user)

        if requests:
            conflicts = {}
            for req in requests:
                req.conflict = [req2.summary for req2 in Request.in_conflict(self.session, req)]
                if req.conflict:
                    conflicts[req.id] = '\n'.join(req.conflict)
            req_list['requests'] = requests
            req_list['conflicts'] = conflicts

        # always add our requests
        req_list['requests'].extend(Request.by_user(self.session, self.user))

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

        if self.user.is_admin:
            req.update_status('APPROVED_ADMIN')
        else:
            req.update_status('ACCEPTED_MANAGER')

        self.session.flush()
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
        self.session.flush()
        return req.status


class Cancel(View):
    """
    Cancel a request
    """

    def render(self):

        req_id = self.request.params.get('request_id')
        req = Request.by_id(self.session, req_id)
        if not req:
            return ''

        req.update_status('CANCELED')
        self.session.flush()
        return req.status


class Export(View):
    """
    Export all requests of a month to csv
    """
    def render(self):

        exported = {}
        if self.user.is_admin:
            requests = Request.get_by_month(self.session)
            data = []
            header = '%s,%s,%s,%s,%s,%s' % ('#', 'user', 'from', 'to', 'number', 'type')
            data.append(header)
            for idx, req in enumerate(requests, start=1):
                data.append('%d,%s' % (idx, req.summarycsv))
            exported = '\n'.join(data)
        return {u'exported': exported}
