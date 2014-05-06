# -*- coding: utf-8 -*-
import re
import logging

from pyramid.settings import asbool

from .base import View, CreateView, EditView, DeleteView

from pyvac.models import User, Group, Countries, Request
from pyvac.helpers.i18n import trans as _
from pyvac.helpers.ldap import LdapCache, hashPassword, randomstring


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
        if use_ldap:
            # synchronise user groups/roles
            User.sync_ldap_info(self.session)
            ldap = LdapCache()
            user_attr = ldap.get_users_units()

        return {u'user_count': User.find(self.session, count=True),
                u'users': User.find(self.session, order_by=[User.dn]),
                'use_ldap': use_ldap,
                'ldap_info': user_attr,
                }


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

        if ldap:
            ldap = LdapCache()
            login = self.get_model().login
            if login:
                view['ldap_user'] = ldap.search_user_by_login(login)
            else:
                view['ldap_user'] = {}
            view['managers'] = ldap.list_manager()
            view['units'] = ldap.list_ou()
            view['countries'] = Countries.all(self.session,
                                              order_by=Countries.name)
            # generate a random password for the user, he must change it later
            password = randomstring()
            log.info('temporary password generated: %s' % password)
            view['password'] = password
            view['view_name'] = self.__class__.__name__.lower()
            view['myself'] = (self.user.id == self.get_model().id)

    def append_groups(self, account):
        exists = []
        group_ids = [int(id) for id in self.request.params.getall('groups')]

        if not group_ids:
            group_ids = [Group.by_name(self.session, u'user').id]

        # only update if there is at least one group provided
        if group_ids:
            for group in account.groups:
                exists.append(group.id)
                if group.id not in group_ids:
                    account.groups.remove(group)

            for group_id in group_ids:
                if group_id not in exists:
                    account.groups.append(Group.by_id(self.session, group_id))

    def set_country(self, account):
        r = self.request
        if 'set_country' in r.params:
            _ct = r.params['set_country']
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
            new_dn = ldap.add_user(account, password=r.params['ldappassword'],
                                   unit=r.params['unit'])
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

            ldap = LdapCache()
            ldap.update_user(account, password=password, unit=unit)

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

            if errors:
                self.request.session.flash('error;%s' % ','.join(errors))

        return len(errors) == 0


class Delete(AccountMixin, DeleteView):
    """
    Delete account
    """

    def delete(self, account):
        # cancel all associated requests for this user
        requests = Request.by_user(self.session, account)
        for req in requests:
            req.update_status('CANCELED')

        super(Delete, self).delete(account)
        if account.ldap_user:
            # delete in ldap
            ldap = LdapCache()
            ldap.delete_user(account.dn)
