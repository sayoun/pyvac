from __future__ import absolute_import

import os
import logging
import hashlib
from base64 import urlsafe_b64encode as encode

import yaml

try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

import ldap
from ldap import dn

log = logging.getLogger(__file__)


class UnknownLdapUser(Exception):
    """ When user was not found in a ldap search """


class LdapWrapper(object):
    """ Simple ldap class wrapper"""
    _conn = None
    _base = None
    _filter = None

    def __init__(self, filename):
        with open(filename) as fdesc:
            conf = yaml.load(fdesc, YAMLLoader)

        url = conf['ldap_url']
        self._base = conf['basedn']
        self._filter = conf['search_filter']

        self.mail_attr = conf['mail_attr']
        self.firstname_attr = conf['firstname_attr']
        self.lastname_attr = conf['lastname_attr']
        self.login_attr = conf['login_attr']
        self.manager_attr = conf['manager_attr']
        self.country_attr = conf['country_attr']

        system_DN = conf['system_dn']
        system_password = conf['system_pass']

        self._conn = ldap.initialize(url)
        self._conn.simple_bind_s(system_DN, system_password)

        log.info('Ldap wrapper initialized')

    def _bind(self, dn, password):
        self._conn.simple_bind_s(dn, password)

    def _search(self, what, retrieve):
        return self._conn.search_s(self._base, ldap.SCOPE_SUBTREE, what,
                                   retrieve)

    def _search_by_item(self, item):
        required_fields = ['cn', 'mail', 'uid', 'givenName', 'sn', 'manager']
        res = self._search(self._filter % item, required_fields)
        if not res:
            raise UnknownLdapUser

        USER_DN, entry = res[0]
        return self.parse_ldap_entry(USER_DN, entry)

    def search_user_by_login(self, login):
        item = 'cn=*%s*' % login
        return self._search_by_item(item)

    def search_user_by_dn(self, user_dn):
        return self._search_by_item(user_dn)

    def parse_ldap_entry(self, user_dn, entry):
        """
        Format ldap entry and parse user_dn to output dict with expected values
        """
        if not user_dn or not entry:
            return

        data = {
            'email': entry[self.mail_attr].pop(),
            'firstname': entry[self.firstname_attr].pop(),
            'lastname': entry[self.lastname_attr].pop(),
            'login': entry[self.login_attr].pop(),
            'manager': entry[self.manager_attr].pop(),
        }
        # save user dn
        data['dn'] = user_dn
        # get country from user_dn
        for rdn in dn.str2dn(user_dn):
            rdn = rdn[0]
            if rdn[0] == self.country_attr:
                data['country'] = rdn[1]

        # get manager cn from data
        for rdn in dn.str2dn(data['manager']):
            rdn = rdn[0]
            if rdn[0] == self.login_attr:
                data['manager'] = rdn[1]

        return data

    def authenticate(self, login, password):
        """ Authenticate user using given credentials """

        user_data = self.search_user_by_login(login)
        # try to bind with password
        self._bind(user_data['dn'], password)
        return user_data


class LdapCache(object):
    """ Ldap cache class """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            raise RuntimeError('Ldap is not initialized')

        return cls._instance

    @classmethod
    def configure(cls, settings):
        cls._instance = cls.from_config(settings)

    @classmethod
    def from_config(cls, config, **kwargs):
        """
        Return a Ldap client object configured from the given configuration.
        """
        return LdapWrapper(config)


def hashPassword(password):
    """
    Generate a password in SSHA format suitable for ldap
    """
    salt = os.urandom(4)
    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt)
