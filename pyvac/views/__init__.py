# -*- coding: utf-8 -*-
from .base import RedirectView
from pyvac.models import VacationType, User


class Index(RedirectView):
    redirect_route = u'login'


class Home(RedirectView):

    redirect_route = u'login'

    def render(self):
        if not self.user:
            return self.redirect()

        _ = self.request.translate

        self.user.rtt = self.user.get_rtt_usage(self.session)

        ret_dict = {'types': [], 'holidays': [], 'sudo_users': []}

        vacation_types = VacationType.by_country(self.session,
                                                 self.user.country)
        for vac in vacation_types:
            ret_dict['types'].append({'name': _(vac.name), 'id': vac.id})

        if self.user.is_admin:
            ret_dict['sudo_users'] = User.for_admin(self.session, self.user)

        if self.request.matched_route:
            matched_route = self.request.matched_route.name
            ret_dict.update({
                'matched_route': matched_route,
                'csrf_token': self.request.session.get_csrf_token()})
            return ret_dict

        ret_dict.update({'csrf_token': self.request.session.get_csrf_token()})
        return ret_dict
