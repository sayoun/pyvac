# -*- coding: utf-8 -*-
from .base import RedirectView
from pyvac.models import VacationType


class Index(RedirectView):
    redirect_route = u'login'


class Home(RedirectView):

    redirect_route = u'login'

    def render(self):
        if not self.user:
            return self.redirect()

        ret_dict = {'types': [vac.name for vac in
                              VacationType.find(self.session,
                                                order_by=[VacationType.name])]}
        if self.request.matched_route:
            matched_route = self.request.matched_route.name
            ret_dict.update({'matched_route': matched_route,
                             'csrf_token': self.request.session.get_csrf_token()})
            return ret_dict

        ret_dict.update({'csrf_token': self.request.session.get_csrf_token()})
        return ret_dict
