from __future__ import absolute_import

import logging
import random
import string
import yaml
from datetime import datetime
from passlib.hash import ldap_salted_sha1

try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

import ldap
from ldap import dn, modlist, SERVER_DOWN, ALREADY_EXISTS

log = logging.getLogger(__file__)


class UnknownLdapUser(Exception):
    """ When user was not found in a ldap search """


class LdapWrapper(object):
    """ Simple ldap class wrapper"""
    _url = None
    _conn = None
    _base = None
    _filter = None

    def __init__(self, filename):
        with open(filename) as fdesc:
            conf = yaml.load(fdesc, YAMLLoader)

        self._url = conf['ldap_url']
        self._base = conf['basedn']
        self._filter = conf['search_filter']

        self.mail_attr = conf['mail_attr']
        self.firstname_attr = conf['firstname_attr']
        self.lastname_attr = conf['lastname_attr']
        self.login_attr = conf['login_attr']
        self.manager_attr = conf['manager_attr']
        self.country_attr = conf['country_attr']

        self.admin_dn = conf['admin_dn']

        self.system_DN = conf['system_dn']
        self.system_password = conf['system_pass']

        self.team_dn = conf['team_dn']
        self.chapter_dn = conf.get('chapter_dn')
        self.default_user = conf.get('default_user', self.system_DN)

        self._conn = ldap.initialize(self._url)
        self._bind(self.system_DN, self.system_password)

        log.info('Ldap wrapper initialized')

    def _bind(self, dn, password):
        """ bind a user in ldap with given password

        ldap does not support unicode for binding
        so we must cast password to utf-8
        """
        log.debug('binding with dn: %s' % dn)
        try:
            self._conn.simple_bind_s(dn, password.encode('utf-8'))
        except SERVER_DOWN:
            self._conn = ldap.initialize(self._url)
            self._conn.simple_bind_s(dn, password.encode('utf-8'))

    def _search(self, what, retrieve):
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        log.debug('searching: %s for: %s' % (what, retrieve))
        return self._conn.search_s(self._base, ldap.SCOPE_SUBTREE, what,
                                   retrieve)

    def _search_admin(self, what, retrieve):
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        return self._conn.search_s(self.admin_dn, ldap.SCOPE_SUBTREE, what,
                                   retrieve)

    def _search_team(self, what, retrieve):
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        return self._conn.search_s(self.team_dn, ldap.SCOPE_SUBTREE, what,
                                   retrieve)

    def _search_chapter(self, what, retrieve):
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        return self._conn.search_s(self.chapter_dn, ldap.SCOPE_SUBTREE, what,
                                   retrieve)

    def _search_by_item(self, item):
        required_fields = ['cn', 'mail', 'uid', 'givenName', 'sn', 'manager',
                           'ou', 'userPassword', 'arrivalDate']
        res = self._search(self._filter % item, required_fields)
        if not res:
            raise UnknownLdapUser

        USER_DN, entry = res[0]
        return self.parse_ldap_entry(USER_DN, entry)

    def search_user_by_login(self, login):
        item = 'cn=*%s*' % login
        return self._search_by_item(item)

    def search_user_by_dn(self, user_dn):
        item = 'cn=*%s*' % self._extract_cn(user_dn)
        return self._search_by_item(item)

    def _extract_country(self, user_dn):
        """ Get country from a user dn """
        for rdn in dn.str2dn(user_dn):
            rdn = rdn[0]
            if rdn[0] == self.country_attr:
                return rdn[1]

    def _extract_cn(self, user_dn):
        """ Get cn from a user dn """
        for rdn in dn.str2dn(user_dn):
            rdn = rdn[0]
            if rdn[0] == self.login_attr:
                return rdn[1]

    def _convert_date(self, date):
        """ Convert a LDAP date entry into a python datetime

        format GeneralizedTime LDAP 1.3.6.1.4.1.1466.115.121.1.24
        example: 199412161032Z
                 yyyyMMddHHmmss
        """
        if not date:
            return

        return datetime.strptime(date, '%Y%m%d%H%M%SZ')

    def _cast_arrivaldate(self, date):
        """ Convert a python datetime into a LDAP date entry

        format GeneralizedTime LDAP 1.3.6.1.4.1.1466.115.121.1.24
        example: 199412161032Z
                 yyyyMMddHHmmss
        """
        if not date:
            return

        return date.strftime('%Y%m%d%H%M%SZ')

    def parse_ldap_entry(self, user_dn, entry):
        """
        Format ldap entry and parse user_dn to output dict with expected values
        """
        if not user_dn or not entry:
            return

        data = {
            'email': entry[self.mail_attr].pop(),
            'lastname': entry[self.lastname_attr].pop(),
            'login': entry[self.login_attr].pop(),
            'manager_dn': '',
            'firstname': '',
        }

        if self.manager_attr in entry:
            data['manager_dn'] = entry[self.manager_attr].pop()

        if self.firstname_attr in entry:
            data['firstname'] = entry[self.firstname_attr].pop()

        if 'ou' in entry:
            data['ou'] = entry['ou'].pop()

        if 'uid' in entry:
            data['uid'] = entry['uid'].pop()

        if 'arrivalDate' in entry:
            data['arrivalDate'] = entry['arrivalDate'].pop()
        else:
            data['arrivalDate'] = None

        # save user dn
        data['dn'] = user_dn
        data['country'] = self._extract_country(user_dn)
        data['manager_cn'] = self._extract_country(data['manager_dn'])
        data['userPassword'] = entry['userPassword'].pop()
        data['arrivalDate'] = self._convert_date(data['arrivalDate'])

        return data

    def authenticate(self, login, password):
        """ Authenticate user using given credentials """

        user_data = self.search_user_by_login(login)

        # try to bind with password
        self._bind(user_data['dn'], password)
        return user_data

    def add_user(self, user, password, unit=None, uid=None):
        """ Add new user into ldap directory """
        # The dn of our new entry/object
        dn = 'cn=%s,c=%s,%s' % (user.login, user.country, self._base)
        log.info('create user %s in ldap' % dn)

        # A dict to help build the "body" of the object
        attrs = {}
        attrs['objectClass'] = ['inetOrgPerson', 'top']
        attrs['employeeType'] = ['Employee']
        attrs['cn'] = [user.login.encode('utf-8')]
        attrs['givenName'] = [user.firstname.encode('utf-8')]
        attrs['sn'] = [user.lastname.encode('utf-8')]
        if uid:
            attrs['uid'] = [uid.encode('utf-8')]
        attrs['mail'] = [user.email.encode('utf-8')]
        if not unit:
            unit = 'development'
        attrs['ou'] = [unit.encode('utf-8')]

        attrs['userPassword'] = [hashPassword(password)]
        attrs['manager'] = [user.manager_dn.encode('utf-8')]

        # Convert our dict for the add-function using modlist-module
        ldif = modlist.addModlist(attrs)
        log.info('sending for dn %r: %r' % (dn, ldif))
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # Do the actual synchronous add-operation to the ldapserver
        self._conn.add_s(dn, ldif)

        # return password to display it to the administrator
        return dn

    def update_user(self, user, password=None, unit=None, arrival_date=None,
                    uid=None):
        """ Update user params in ldap directory """
        # convert fields to ldap fields
        # retrieve them from model as it was updated before
        fields = {
            'mail': [user.email.encode('utf-8')],
            'givenName': [user.firstname.encode('utf-8')],
            'sn': [user.lastname.encode('utf-8')],
            'manager': [user.manager_dn.encode('utf-8')],
        }
        if password:
            fields['userPassword'] = password

        if unit:
            fields['ou'] = [unit.encode('utf-8')]

        if arrival_date:
            fields['arrivalDate'] = [self._cast_arrivaldate(arrival_date)]

        if uid:
            fields['uid'] = [uid.encode('utf-8')]

        # dn of object we want to update
        dn = 'cn=%s,c=%s,%s' % (user.login, user.country, self._base)
        log.info('updating user %s from ldap' % dn)

        # retrieve current user information
        required = ['objectClass', 'employeeType', 'cn', 'givenName', 'sn',
                    'manager', 'mail', 'ou', 'uid', 'userPassword',
                    'arrivalDate']
        item = 'cn=*%s*' % user.login
        res = self._search(self._filter % item, required)
        USER_DN, entry = res[0]

        old = {}
        new = {}
        # for each field to be updated
        for field in fields:
            # get old value
            old[field] = entry.get(field, '')
            # set new value
            new[field] = fields[field]

        # Convert place-holders for modify-operation using modlist-module
        ldif = modlist.modifyModlist(old, new)
        if ldif:
            # rebind with system dn
            self._bind(self.system_DN, self.system_password)
            log.info('sending for dn %r: %r' % (dn, ldif))
            # Do the actual modification if needed
            self._conn.modify_s(dn, ldif)

    def delete_user(self, user_dn):
        """ Delete user from ldap """
        log.info('deleting user %s from ldap' % user_dn)

        # retrieve current user information
        required = ['employeeType']
        item = 'cn=*%s*' % self._extract_cn(user_dn)
        res = self._search(self._filter % item, required)
        USER_DN, entry = res[0]

        old = {
            'employeeType': entry['employeeType'],
        }
        new = {
            'employeeType': 'Inactive',
        }

        # Convert place-holders for modify-operation using modlist-module
        ldif = modlist.modifyModlist(old, new)
        if ldif:
            # rebind with system dn
            self._bind(self.system_DN, self.system_password)
            log.info('sending for dn %r: %r' % (user_dn, ldif))
            # Do the actual modification if needed
            self._conn.modify_s(user_dn, ldif)

    def update_team(self, team, members):
        """ Update team members in ldap directory """
        # dn of object we want to update
        dn = 'cn=%s,%s' % (team, self.team_dn)
        log.info('updating team %s from ldap' % team)

        # retrieve current team members
        team_members = self.get_team_members(team)

        old = {'member': team_members}
        new = {'member': members}

        # Convert place-holders for modify-operation using modlist-module
        ldif = modlist.modifyModlist(old, new)
        if ldif:
            # rebind with system dn
            self._bind(self.system_DN, self.system_password)
            log.info('sending for dn %r: %r' % (dn, ldif))
            # Do the actual modification if needed
            self._conn.modify_s(dn, ldif)

    def get_hr_by_country(self, country):
        """ Get hr mail of country for a user_dn"""
        what = '(member=*)'
        results = self._search_admin(what, None)
        for USER_DN, res_entry in results:
            for entry in res_entry['member']:
                item = self._extract_country(entry)
                if item == country:
                    # found valid hr user for this country
                    login = self._extract_cn(entry)
                    user_data = self.search_user_by_login(login)
                    return user_data

        # security if no admin per country found, take the last one
        login = self._extract_cn(entry)
        user_data = self.search_user_by_login(login)
        return user_data

    def list_ou(self):
        """ Retrieve available organisational units """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all users so we can extract OU
        required = None
        item = '(member=*)'
        res = self._search_team(item, required)
        units = []
        for USER_DN, entry in res:
            units.append(USER_DN)
        # only return unique entries
        return set(units)

    def list_teams(self):
        """ Retrieve available teams """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all teams so we can extract members
        required = None
        item = '(member=*)'
        res = self._search_team(item, required)
        teams = {}
        for USER_DN, entry in res:
            if 'manager' not in entry['cn'][0]:
                teams[entry['cn'][0]] = entry['member']
        return teams

    def list_chapters(self):
        """ Retrieve available chapters """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all chapters so we can extract members
        required = None
        item = '(member=*)'
        res = self._search_chapter(item, required)
        chapters = {}
        for USER_DN, entry in res:
            if 'manager' not in entry['cn'][0]:
                chapters[entry['cn'][0]] = entry['member']
        return chapters

    def list_manager(self):
        """ Retrieve available managers dn """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all users so we can extract OU
        required = None
        item = '(&(member=*)(cn=manager*))'
        res = self._search_team(item, required)
        USER_DN, entry = res[0]
        managers = entry['member']
        # only return unique entries
        return sorted(managers)

    def list_admin(self):
        """ Retrieve available admins dn """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all users so we can extract OU
        required = None
        item = '(member=*)'
        res = self._search_admin(item, required)
        USER_DN, entry = res[0]
        managers = entry['member']
        # only return unique entries
        return sorted(managers)

    def list_arrivals_country(self, country):
        """ Retrieve users arrival dates """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all users so we can extract OU
        required = ['arrivalDate']
        item = 'cn=*'
        res = self._conn.search_s('c=%s,%s' % (country, self._base),
                                  ldap.SCOPE_SUBTREE,
                                  self._filter % item, required)
        arrivals = {}
        for USER_DN, entry in res:
            arrival = entry.get('arrivalDate', [None])[0]
            arrivals[USER_DN] = self._convert_date(arrival)
        # only return unique entries
        return arrivals

    def list_active_users(self):
        """ Retrieve available teams """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all users so we can extract OU
        required = ['cn']
        item = '|(c:dn:=zh)(c:dn:=fr)(c:dn:=lu)(c:dn:=us)'
        res = self._conn.search_s('%s' % self._base,
                                  ldap.SCOPE_SUBTREE,
                                  self._filter % item, required)

        users = []
        for USER_DN, entry in res:
            cn = entry.get('cn', [None])[0]
            users.append(cn)
        # only return unique entries
        return users

    def get_users_units(self):
        """ Retrieve ou for all users """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all users so we can extract OU
        required = ['ou']
        item = 'cn=*'
        res = self._search(item, required)
        users_units = {}
        for USER_DN, entry in res:
            if USER_DN not in users_units:
                users_units[USER_DN] = {}
            if 'ou' in entry:
                users_units[USER_DN]['ou'] = entry['ou'][0]
        return users_units

    def get_team_members(self, team):
        """ Retrieve team members list """
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # retrieve all teams so we can extract members
        required = None
        item = '(&(cn=*%s*)(member=*))' % team
        res = self._search_team(item, required)
        _, entry = res[0]
        return entry['member']

    def create_team(self, team):
        """Create a team."""
        if not team:
            log.error('cannot create empty team')
            return

        # member field cannot be empty so we always assign a default user
        entry = {
            'objectClass': ['groupOfNames', 'top'],
            'cn': '%s' % team,
            'member': [self.default_user],
        }
        ladd = modlist.addModlist(entry)
        team_dn = 'cn=%s,dc=teams,dc=origin,dc=gandi,dc=net' % team
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # Do the actual synchronous add-operation to the ldapserver
        self._conn.add_s(team_dn, ladd)
        log.info('team %s created' % team)

    def delete_team(self, team):
        """Delete a team."""
        if not team:
            log.error('cannot delete empty team')
            return

        team_dn = 'cn=%s,dc=teams,dc=origin,dc=gandi,dc=net' % team
        # rebind with system dn
        self._bind(self.system_DN, self.system_password)
        # Do the actual synchronous add-operation to the ldapserver
        self._conn.delete_s(team_dn)
        log.info('team %s deleted' % team)


class LdapCache(object):
    """ Ldap cache class singleton """
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
    """ Generate a password in SSHA format suitable for ldap """
    return ldap_salted_sha1.encrypt(password)


def randomstring(length=8):
    """ Generates a random ascii string """
    chars = string.letters + string.digits

    # Generate string from population
    data = [random.choice(chars) for _ in xrange(length)]

    return ''.join(data)
