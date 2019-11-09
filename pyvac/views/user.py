# -*- coding: utf-8 -*-
"""
Pyvac User Management Views.

Used by the connected user to edit its account.
"""
from pyvac.models import User
from pyvac.helpers.i18n import trans as _

from .account import AccountMixin
from .base import EditView


class UserMixin(AccountMixin):
    redirect_route = 'home'

    def get_model(self):
        return self.user

    def update_view(self, model, view):
        pass


class Edit(UserMixin, EditView):
    """
    Edit connected user
    """


class ChangePassword(UserMixin, EditView):
    """
    Change current user password
    """

    def validate(self, model, errors):
        r = self.request

        if not User.by_credentials(self.session, model.login,
                                   r.params['current_password']):
            errors.append(_('current password is not correct'))
        elif r.params['user.password'] == r.params['current_password']:
            errors.append(_('password is inchanged'))

        if r.params['user.password'] != r.params['confirm_password']:
            errors.append(_('passwords do not match'))

        return len(errors) == 0
