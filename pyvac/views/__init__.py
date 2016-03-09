# -*- coding: utf-8 -*-
from .base import RedirectView
from pyvac.helpers.holiday import get_holiday
from pyvac.models import VacationType, User, Request


class Index(RedirectView):
    redirect_route = u'login'


class Home(RedirectView):

    redirect_route = u'login'

    def render(self):
        if not self.user:
            return self.redirect()

        _ = self.request.translate

        self.user.rtt = self.user.get_rtt_usage(self.session)
        self.user.cp = self.user.get_cp_usage(self.session)

        holidays = get_holiday(self.user)

        ret_dict = {'types': [], 'holidays': holidays, 'sudo_users': [],
                    'futures_pending': [], 'futures_approved': []}

        vacation_types = VacationType.by_country(self.session,
                                                 self.user.country)
        for vac in vacation_types:
            if vac.visibility and self.user.role not in vac.visibility:
                continue
            ret_dict['types'].append({'name': _(vac.name), 'id': vac.id})

        if self.user.is_admin:
            ret_dict['sudo_users'] = User.for_admin(self.session, self.user)

        futures_pending = [timestamp
                           for req in
                           Request.by_user_future_pending(self.session,
                                                          self.user)
                           for timestamp in req.timestamps]
        ret_dict['futures_pending'] = futures_pending
        futures_approved = [timestamp
                            for req in
                            Request.by_user_future_approved(self.session,
                                                            self.user)
                            for timestamp in req.timestamps]
        ret_dict['futures_approved'] = futures_approved

        exception_info_tooltip = """\
This type is for events which are not covered by other types: \
wedding, funeral, etc.

Providing a reason for this request is mandatory.
"""
        ret_dict['exception_info_tooltip'] = _(exception_info_tooltip)

        if self.request.matched_route:
            matched_route = self.request.matched_route.name
            ret_dict.update({
                'matched_route': matched_route,
                'csrf_token': self.request.session.get_csrf_token()})
            return ret_dict

        ret_dict.update({'csrf_token': self.request.session.get_csrf_token()})
        return ret_dict
