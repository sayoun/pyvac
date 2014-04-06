# -*- coding: utf-8 -*-
import logging

from pyramid.httpexceptions import HTTPFound
from pyramid.url import resource_url, route_url
from pyramid.security import remember, forget
from pyramid.settings import asbool

# from pyvac.helpers.i18n import trans as _
from pyvac.models import User
from pyvac.helpers.ldap import UnknownLdapUser

from .base import View

from ldap import INVALID_CREDENTIALS, SERVER_DOWN

log = logging.getLogger(__name__)


class Login(View):

    def render(self):

        login_url = resource_url(self.request.context, self.request, 'login')
        referrer = self.request.url
        # never use the login form itself as came_from
        if referrer == login_url:
            referrer = '/'
        came_from = self.request.params.get('came_from', referrer)
        if came_from == '/':
            came_from = '/home'

        login = self.request.params.get('login', '')
        if 'submit' in self.request.params:
            password = self.request.params.get('password', u'')
            if password:
                settings = self.request.registry.settings
                ldap = False
                if 'pyvac.use_ldap' in settings:
                    ldap = asbool(settings.get('pyvac.use_ldap'))

                try:
                    user = User.by_credentials(self.session, login,
                                               password, ldap)
                    if user is not None:
                        log.info('login %r succeed' % login)
                        headers = remember(self.request, login)
                        return HTTPFound(location=came_from,
                                         headers=headers)
                    else:
                        msg = 'Invalid credentials.'
                        self.request.session.flash('error;%s' % msg)
                except SERVER_DOWN:
                    msg = 'Cannot reach ldap server.'
                    self.request.session.flash('error;%s' % msg)
                except INVALID_CREDENTIALS:
                    msg = 'Invalid credentials.'
                    self.request.session.flash('error;%s' % msg)
                except UnknownLdapUser:
                    msg = 'Unknown ldap user %s' % login
                    self.request.session.flash('error;%s' % msg)

        return {'came_from': came_from,
                'csrf_token': self.request.session.get_csrf_token(),
                }


class Logout(View):

    def render(self):

        return HTTPFound(location=route_url('index', self.request),
                         headers=forget(self.request))
