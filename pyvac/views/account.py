# -*- coding: utf-8 -*-
import re
import base64
import logging
from datetime import datetime

from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPFound
from pyramid.url import route_url

from .base import View, CreateView, EditView, DeleteView

from pyvac.models import User, Group, Countries
from pyvac.helpers.i18n import trans as _
from pyvac.helpers.ldap import (
    LdapCache, hashPassword, randomstring, UnknownLdapUser,
    ALREADY_EXISTS,
)


log = logging.getLogger(__name__)


class MandatoryLdapPassword(Exception):
    """ Raise when no password has been provided when creating a user """


class List(View):
    """
    List all user accounts
    """
    def render(self):

        settings = self.request.registry.settings
        use_ldap = False
        if 'pyvac.use_ldap' in settings:
            use_ldap = asbool(settings.get('pyvac.use_ldap'))

        user_attr = {}
        users_teams = {}
        active_users = []
        if use_ldap:
            # synchronise user groups/roles
            User.sync_ldap_info(self.session)
            ldap = LdapCache()

            user_attr = ldap.get_users_units()
            users_teams = {}
            for team, members in ldap.list_teams().iteritems():
                for member in members:
                    users_teams.setdefault(member, []).append(team)

            active_users = ldap.list_active_users()

        return {u'user_count': User.find(self.session, count=True),
                u'users': User.find(self.session, order_by=[User.dn]),
                'use_ldap': use_ldap,
                'ldap_info': user_attr,
                'users_teams': users_teams,
                'active_users': active_users,
                }


class ListPool(View):
    """
    List all user pool
    """
    ignore_users = []

    def render(self):
        if self.user and not self.user.is_admin:
            return HTTPFound(location=route_url('home', self.request))

        country = Countries.by_name(self.session, self.user.country)
        users = User.by_country(self.session, country.id)

        today = datetime.now()
        data = []
        rtt_usage = {}
        cp_usage = {}
        for user in users:
            if self.user.country == 'fr':
                rtts = user.get_rtt_usage(self.session)
                if rtts:
                    rtt_usage[user.login] = rtts['left']

            cps = user.get_cp_usage(self.session, today=today, taken_end=today)
            total = 0
            if cps:
                total = cps['restant']['left'] + cps['acquis']['left']
                if self.user.country == 'fr':
                    total = total + cps['n_1']['left'] + cps.get('extra', {}).get('left', 0) # noqa
            cp_usage[user.login] = total
            if self.user.country == 'fr':
                if user.login not in self.ignore_users:
                    data.append('%s,%s,%s,%s' %
                                (user.login,
                                 rtt_usage.get(user.login, 0),
                                 cps.get('extra', {}).get('left', 0) if cps else 0, # noqa
                                 cps['restant']['left'] if cps else 0,
                                 ))

        if data:
            # sort list by name
            data = sorted(data)
            header = ('%s,%s,%s,%s' % ('Login', 'RTT', 'CP N-1', 'CP N'))
            data.insert(0, header)

        ret = {u'user_count': User.find(self.session, count=True),
               u'users': users,
               u'today': today,
               u'cp_usage': cp_usage,
               u'exported': '\n'.join(data)}

        if self.user.country == 'fr':
            ret['rtt_usage'] = rtt_usage

        return ret


class AccountMixin:
    model = User
    matchdict_key = 'user_id'
    redirect_route = 'list_account'

    def update_view(self, model, view):
        settings = self.request.registry.settings
        ldap = False
        if 'pyvac.use_ldap' in settings:
            ldap = asbool(settings.get('pyvac.use_ldap'))

        if view['errors']:
            self.request.session.flash('error;%s' % ','.join(view['errors']))

        view['groups'] = Group.all(self.session, order_by=Group.name)
        view['managers'] = User.by_role(self.session, 'manager')
        view['countries'] = Countries.all(self.session,
                                          order_by=Countries.name)
        if ldap:
            ldap = LdapCache()
            login = self.get_model().login
            view['ldap_user'] = {}
            if login:
                try:
                    view['ldap_user'] = ldap.search_user_by_login(login)
                except UnknownLdapUser:
                    msg = 'Unknown ldap user %s' % login
                    self.request.session.flash('error;%s' % msg)

            view['managers'] = ldap.list_manager()
            view['units'] = ldap.list_ou()

            view['teams'] = ldap.list_teams()
            uteams = {}
            for team, members in view['teams'].iteritems():
                for member in members:
                    uteams.setdefault(member, []).append(team)
            view['user_teams'] = uteams.get(view['ldap_user'].get('dn'), [])

            # generate a random password for the user, he must change it later
            password = randomstring()
            log.debug('temporary password generated: %s' % password)
            view['password'] = password
            view['view_name'] = self.__class__.__name__.lower()
            view['myself'] = (self.user.id == self.get_model().id)

            jpeg = view['ldap_user'].get('jpegPhoto')
            if jpeg:
                view['ldap_user']['photo'] = base64.b64encode(jpeg)

    def append_groups(self, account):
        settings = self.request.registry.settings
        use_ldap = False
        if 'pyvac.use_ldap' in settings:
            use_ldap = asbool(settings.get('pyvac.use_ldap'))
        if use_ldap:
            # update groups only for non LDAP users
            return

        exists = []
        group_ids = [int(id) for id in self.request.params.getall('groups')]

        if not group_ids:
            # ensure that account has at least user group otherwise
            # he cannot access anything
            group_ids = [Group.by_name(self.session, u'user').id]

        # only update if there is at least one group provided
        if group_ids:
            # cast as list because of iterator for will only loop on first one
            account_groups = list(account.groups)
            for group in account_groups:
                exists.append(group.id)
                if group.id not in group_ids:
                    if group.name != 'sudoer':
                        account.groups.remove(group)

            for group_id in group_ids:
                if group_id not in exists:
                    account.groups.append(Group.by_id(self.session, group_id))

    def set_country(self, account):
        r = self.request
        if 'set_country' in r.params:
            _ct = r.params['set_country']
        else:
            # country cannot be edited by user, only admin
            # so default to logged user country
            if self.user:
                _ct = self.user.country
            else:
                _ct = u'fr'
        country = Countries.by_name(self.session, _ct)
        account._country = country


class Create(AccountMixin, CreateView):
    """
    Create account
    """

    def save_model(self, account):
        super(Create, self).save_model(account)
        self.set_country(account)
        self.append_groups(account)

        if 'disable_rtt' in self.request.params:
            account.add_feature('disable_rtt', save=True)
        else:
            account.del_feature('disable_rtt', save=True)

        settings = self.request.registry.settings
        ldap = False
        if 'pyvac.use_ldap' in settings:
            ldap = asbool(settings.get('pyvac.use_ldap'))

        if ldap:
            # create in ldap
            r = self.request
            ldap = LdapCache()
            if 'ldappassword' not in r.params:
                raise MandatoryLdapPassword()

            uid = None
            if 'user.uid' in r.params and r.params['user.uid']:
                uid = r.params['user.uid']

            try:
                new_dn = ldap.add_user(account,
                                       password=r.params['ldappassword'],
                                       unit=r.params.get('unit'), uid=uid)
                msg = ('User %s created in pyvac and ldap' % account.login)
                self.request.session.flash('info;%s' % msg)
            except ALREADY_EXISTS:
                # already exists in ldap, only retrieve the dn
                new_dn = 'cn=%s,c=%s,%s' % (account.login, account.country,
                                            ldap._base)
                msg = ('User %s already exists in ldap, created only in pyvac'
                       % account.login)
                log.info(msg)
                self.request.session.flash('info;%s' % msg)

            # update dn
            account.dn = new_dn

        if self.user and not self.user.is_admin:
            self.redirect_route = 'list_request'

    def validate(self, model, errors):
        r = self.request
        if 'user.password' in r.params:
            if r.params['user.password'] != r.params['confirm_password']:
                errors.append(_('passwords do not match'))

        if 'user.login' not in r.params:
            if 'user.ldap_user' in r.params and r.params['user.ldap_user']:
                r_space = re.compile(r'\s+')
                # generate login for ldap user
                login = '%s.%s' % (r.params['user.firstname'].strip().lower(),
                                   r.params['user.lastname'].strip().lower())
                # remove all spaces
                login = r_space.sub('', login)
                model.login = login
            else:
                errors.append(_('login is required'))

        return len(errors) == 0


class Edit(AccountMixin, EditView):
    """
    Edit account
    """

    def save_model(self, account):
        super(Edit, self).update_model(account)
        self.set_country(account)
        self.append_groups(account)

        if 'disable_rtt' in self.request.params:
            account.add_feature('disable_rtt', save=True)
        else:
            account.del_feature('disable_rtt', save=True)

        settings = self.request.registry.settings
        ldap = False
        if 'pyvac.use_ldap' in settings:
            ldap = asbool(settings.get('pyvac.use_ldap'))

        if ldap:
            # update in ldap
            r = self.request
            password = None
            if 'user.password' in r.params and r.params['user.password']:
                password = [hashPassword(r.params['user.password'])]

            unit = None
            if 'unit' in r.params and r.params['unit']:
                unit = r.params['unit']

            arrival_date = None
            if 'arrival_date' in r.params and r.params['arrival_date']:
                # cast to datetime
                arrival_date = datetime.strptime(r.params['arrival_date'],
                                                 '%d/%m/%Y')
            uid = None
            if 'user.uid' in r.params and r.params['user.uid']:
                uid = r.params['user.uid']

            if (r.params.get('remove_photo', 'no') == 'yes'):
                photo = ''
            else:
                try:
                    r.params['photofile'].file.seek(0)
                    photo = r.params['photofile'].file.read()
                except:
                    photo = None

            ldap = LdapCache()
            ldap.update_user(account, password=password, unit=unit,
                             arrival_date=arrival_date, uid=uid,
                             photo=photo)

            # update teams
            uteams = {}
            for team, members in ldap.list_teams().iteritems():
                for member in members:
                    uteams.setdefault(member, []).append(team)
            user_teams = uteams.get(account.dn, [])

            # add to new teams
            for team in r.params.getall('teams'):
                members = ldap.get_team_members(team)
                if account.dn not in members:
                    members.append(account.dn.encode('utf-8'))
                    ldap.update_team(team, members)

            # remove from old teams
            for team in user_teams:
                if team not in r.params.getall('teams'):
                    members = ldap.get_team_members(team)
                    if account.dn in members:
                        members.remove(account.dn)
                    ldap.update_team(team, members)

        if self.user and not self.user.is_admin:
            self.redirect_route = 'list_request'

    def validate(self, model, errors):
        r = self.request
        settings = r.registry.settings
        ldap = False

        if 'pyvac.use_ldap' in settings:
            ldap = asbool(settings.get('pyvac.use_ldap'))

        if 'current_password' in r.params and r.params['current_password']:
            if not User.by_credentials(self.session, model.login,
                                       r.params['current_password'], ldap):
                errors.append(_(u'current password is not correct'))
            elif r.params['user.password'] == r.params['current_password']:
                errors.append(_(u'password is unchanged'))

            if r.params['user.password'] != r.params['confirm_password']:
                errors.append(_(u'passwords do not match'))

        if (r.params.get('remove_photo', 'no') == 'no'):
            try:
                photo = r.POST['photofile'].file.read()
                photo_size = len(photo)
                if photo_size > 200000:
                    errors.append(_(u'Invalid photo size: %d' % photo_size))
            except:
                pass

        if errors:
            self.request.session.flash('error;%s' % ','.join(errors))

        return len(errors) == 0


class Delete(AccountMixin, DeleteView):
    """
    Delete account
    """

    def delete(self, account):
        # cancel all associated requests for this user
        requests = account.requests
        for req in requests:
            req.update_status('CANCELED')
            # delete all request history entries for this user
            # otherwise it will raise a integrity error
            for entry in req.history:
                self.session.delete(entry)

        # cancel associated password recovery attempts for this user
        for item in account.recovery:
            self.session.delete(item)

        super(Delete, self).delete(account)
        if account.ldap_user:
            # delete in ldap
            ldap = LdapCache()
            try:
                ldap.delete_user(account.dn)
            except IndexError:
                log.info('User %s seems already deleted in ldap' % account.dn)


def includeme(config):
    """
    Pyramid includeme file for the :class:`pyramid.config.Configurator`
    """
    settings = config.registry.settings

    if 'pyvac.export_pool.ignore_users' in settings:
        ignore_users = settings['pyvac.export_pool.ignore_users']
        ListPool.ignore_users = ignore_users
        log.info('Loaded ListPool ignore_users: %s' % ListPool.ignore_users)
