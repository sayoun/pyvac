# -*- coding: utf-8 -*-
import uuid
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta

from pyramid.httpexceptions import HTTPFound
from pyramid.url import resource_url, route_url
from pyramid.security import remember, forget
from pyramid.settings import asbool

from pyvac.helpers.i18n import trans as _
from pyvac.models import User, PasswordRecovery, Sudoer
from pyvac.helpers.ldap import (
    UnknownLdapUser, LdapCache, hashPassword,
)

from .base import View

from ldap import INVALID_CREDENTIALS, SERVER_DOWN

log = logging.getLogger(__name__)


class Login(View):

    blacklist_users = []

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
                    if login in self.blacklist_users:
                        raise INVALID_CREDENTIALS
                    user = User.by_credentials(self.session, login,
                                               password, ldap)
                    if user is not None:
                        log.info('login %r succeed' % user.login)
                        headers = remember(self.request, user.login)

                        # check for available users for sudo
                        sudoers = Sudoer.alias(self.session, user)
                        if sudoers:
                            location = route_url('sudo', self.request)
                            return HTTPFound(location=location,
                                             headers=headers)

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


class ResetPassword(View):

    def render(self):

        if 'submit' in self.request.params:
            email = self.request.params.get('email', '')
            user = User.by_email(self.session, email)
            if user:
                passhash = uuid.uuid4().hex
                date_end = datetime.now() + relativedelta(seconds=86400)
                # create hash entry in database with a TTL of 1 day
                entry = PasswordRecovery(user_id=user.id,
                                         hash=passhash,
                                         date_end=date_end)
                self.session.add(entry)
                self.session.flush()

                # call celery send mail task directly
                from celery.registry import tasks
                from celery.task import subtask
                req_task = tasks['worker_mail']

                settings = self.request.registry.settings
                sender = 'pyvac@localhost'
                if 'pyvac.password.sender.mail' in settings:
                    sender = settings['pyvac.password.sender.mail']

                data = {
                    'sender': sender,
                    'target': user.email,
                    'subject': 'Password Recovery',
                    'content': """Hello,

we send you this mail because you requested a password reset, to proceed please click the link below:
%s

Reminder, your login is: %s

""" % (route_url('change_password', self.request, passhash=passhash), user.login)
                }

                subtask(req_task).delay(data=data)

                msg = 'Mail sent to %s for password recovery.' % user.email
                self.request.session.flash('info;%s' % msg)
                return HTTPFound(location=route_url('login', self.request))

        return {}


class ChangePassword(View):

    def render(self):

        passhash = self.request.matchdict['passhash']
        entry = PasswordRecovery.by_hash(self.session, passhash)
        if not entry:
            return HTTPFound(location=route_url('login', self.request))

        if entry.expired:
            msg = 'This password recovery request have expired.'
            self.request.session.flash('error;%s' % msg)
            self.session.delete(entry)
        else:
            errors = []
            if 'form.submitted' in self.request.params:
                r = self.request
                settings = self.request.registry.settings
                ldap = False
                if 'pyvac.use_ldap' in settings:
                    ldap = asbool(settings.get('pyvac.use_ldap'))

                if not len(r.params['user.password']):
                    errors.append(_(u'password cannot be empty'))

                if r.params['user.password'] != r.params['confirm_password']:
                    errors.append(_(u'passwords do not match'))

                if errors:
                    self.request.session.flash('error;%s' % ','.join(errors))

                if not errors:
                    # change user password
                    if ldap:
                        # update in ldap
                        password = [hashPassword(r.params['user.password'])]
                        ldap = LdapCache()
                        ldap.update_user(entry.user, password=password)
                    else:
                        # update locally
                        entry.user.password = r.params['user.password']

                    msg = 'Password successfully changed'
                    self.request.session.flash('info;%s' % msg)
                    self.session.delete(entry)
                    return HTTPFound(location=route_url('login', self.request))

        return {'user': entry.user}


class Sudo(View):

    def render(self):
        if not self.user.is_sudoer(self.session):
            log.info("user '%s' tried to access sudo but is not authorized" %
                     self.user.login)
            return HTTPFound(location=route_url('home', self.request))

        req = self.request
        if req.method == 'POST' and 'continue' in req.params:
            headers = None
            target_id = int(req.params.get('sudo', self.user.id))
            if target_id != self.user.id:
                target = User.by_id(self.session, target_id)
                if not target:
                    errors = ['Cannot find user with id %d' % target_id]
                    self.request.session.flash('error;%s' % ','.join(errors))

                log.info("user '%s' will sudo to user '%s'" %
                         (self.user.login, target.login))
                headers = remember(self.request, target.login)
            return HTTPFound(location=route_url('home', self.request),
                             headers=headers)

        return {'user': self.user}


def includeme(config):
    """
    Pyramid includeme file for the :class:`pyramid.config.Configurator`
    """
    settings = config.registry.settings

    if 'pyvac.blacklist_users' in settings:
        blacklist_users = settings['pyvac.blacklist_users']
        Login.blacklist_users = blacklist_users
        log.info('Loaded Login blacklist_users: %s' % Login.blacklist_users)
