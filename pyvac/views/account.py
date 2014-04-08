# -*- coding: utf-8 -*-
import logging

from pyramid.settings import asbool

from .base import View, CreateView, EditView, DeleteView

from pyvac.models import User, Group
from pyvac.helpers.i18n import trans as _
from pyvac.helpers.ldap import LdapCache


log = logging.getLogger(__name__)


class List(View):
    """
    List all user accounts
    """
    def render(self):

        return {u'user_count': User.find(self.session, count=True),
                u'users': User.find(self.session),
                }


class AccountMixin:
    model = User
    matchdict_key = 'user_id'
    redirect_route = 'list_account'

    def update_view(self, model, view):
        view['groups'] = Group.all(self.session, order_by=Group.name)
        view['managers'] = User.by_role(self.session, 'manager')

    def append_groups(self, account):
        exists = []
        group_ids = [int(id) for id in self.request.params.getall('groups')]

        # only update if there is at least one group provided
        if group_ids:
            for group in account.groups:
                exists.append(group.id)
                if group.id not in group_ids:
                    account.groups.remove(group)

            for group_id in self.request.params.getall('groups'):
                if group_id not in exists:
                    account.groups.append(Group.by_id(self.session, group_id))


class Create(AccountMixin, CreateView):
    """
    Create account
    """

    def save_model(self, account):
        super(Create, self).update_model(account)
        self.append_groups(account)

    def validate(self, model, errors):
        r = self.request
        if r.params['user.password'] != r.params['confirm_password']:
            errors.append(_('passwords do not match'))
        return len(errors) == 0


class Edit(AccountMixin, EditView):
    """
    Edit account
    """

    def save_model(self, account):
        super(Edit, self).update_model(account)
        self.append_groups(account)
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
                errors.append(_(u'password is inchanged'))

            if r.params['user.password'] != r.params['confirm_password']:
                errors.append(_(u'passwords do not match'))

            if errors:
                self.request.session.flash('error;%s' % ','.join(errors))

        return len(errors) == 0


class Delete(AccountMixin, DeleteView):
    """
    Delete account
    """
