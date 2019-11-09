# -*- coding: utf-8 -*-
from .base import RedirectView
from pyvac.helpers.holiday import get_holiday
from pyvac.models import VacationType, User, Request


class Index(RedirectView):
    redirect_route = 'login'


class Home(RedirectView):

    redirect_route = 'login'

    def render(self):
        if not self.user:
            return self.redirect()

        _ = self.request.translate

        holidays = get_holiday(self.user)

        ret_dict = {'types': [], 'holidays': holidays, 'sudo_users': [],
                    'futures_pending': [], 'futures_approved': []}

        vacation_types = VacationType.by_country(self.session,
                                                 self.user.country)
        for vac in vacation_types:
            if vac.visibility and self.user.role not in vac.visibility:
                continue
            # disable RTT for user with feature flag disable_rtt
            if vac.name == 'RTT' and self.user.has_feature('disable_rtt'):
                continue
            ret_dict['types'].append({'name': _(vac.name), 'id': vac.id})

        if self.user.is_admin:
            ret_dict['sudo_users'] = User.for_admin(self.session, self.user)
            managed_users = User.managed_users(self.session, self.user)
            if managed_users:
                ret_dict['sudo_users'].extend(managed_users)
            # special case where LU admin need to have RTT option
            rtt_vacation = VacationType.by_name(self.session, 'RTT')
            rtt_type = {'name': _('RTT'), 'id': rtt_vacation.id}
            if rtt_type not in ret_dict['types']:
                ret_dict['types'].append(rtt_type)
            # remove duplicate entries
            ret_dict['sudo_users'] = list(set(ret_dict['sudo_users']))

        # LU can use their CP if it was on a non working day
        ret_dict['recovered_cp'] = self.user.get_lu_holiday()

        futures_breakdown = [timestamp
                             for req in
                             Request.by_user_future_breakdown(self.session,
                                                              self.user)
                             for timestamp in req.timestamps]
        ret_dict['futures_breakdown'] = futures_breakdown
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

        recovered_info_tooltip = """\
This type is for holidays which were on a non working day.

You can use them up to 3 months after their date to make a leave request.
Request must be only for 1 day at a time, and not partial (only Full).
"""
        ret_dict['recovered_info_tooltip'] = _(recovered_info_tooltip)

        if self.request.matched_route:
            matched_route = self.request.matched_route.name
            ret_dict.update({
                'matched_route': matched_route,
                'csrf_token': self.request.session.get_csrf_token()})
            return ret_dict

        ret_dict.update({'csrf_token': self.request.session.get_csrf_token()})
        return ret_dict
