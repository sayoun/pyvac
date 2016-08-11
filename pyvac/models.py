"""This module contains all internal database objects and methods."""
# -*- coding: utf-8 -*-

import re
import logging
import json
import math
from datetime import datetime, timedelta

from pyramid.settings import asbool, aslist
from dateutil.relativedelta import relativedelta
import cryptacular.bcrypt
from sqlalchemy import (Table, Column, ForeignKey, Enum,
                        Integer, Float, Boolean, Unicode, DateTime,
                        UnicodeText)
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import relationship, synonym

import yaml
try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

from .helpers.sqla import (Database, SessionFactory, ModelError,
                           create_engine as create_engine_base,
                           dispose_engine as dispose_engine_base
                           )

from pyvac.helpers.ldap import LdapCache
from pyvac.helpers.i18n import translate as _
from pyvac.helpers.calendar import addToCal
from pyvac.helpers.util import daterange
from pyvac.helpers.holiday import utcify, get_lu_recovered_holiday

log = logging.getLogger(__file__)
crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

DBSession = lambda: SessionFactory.get('pyvac')() # noqa
Base = Database.register('pyvac')

re_email = re.compile(r'^[^@]+@[a-z0-9]+[-.a-z0-9]+\.[a-z]+$', re.I)


class FirstCycleException(Exception):
    """Raised when impossible to retrieve cycle boundaries."""


def create_engine(settings, prefix='sqlalchemy.', scoped=False):
    """Create database engine."""
    return create_engine_base('pyvac', settings, prefix, scoped)


def dispose_engine():
    """Dispose database engine."""
    dispose_engine_base


class Permission(Base):
    """Describe a user permission."""

    name = Column(Unicode(255), nullable=False, unique=True)


group__permission = Table('group__permission', Base.metadata,
                          Column('group_id', Integer, ForeignKey('group.id')),
                          Column('permission_id',
                                 Integer, ForeignKey('permission.id'))
                          )


class Group(Base):
    """Describe user's groups."""

    name = Column(Unicode(255), nullable=False, unique=True)
    permissions = relationship(Permission, secondary=group__permission,
                               lazy='select')

    @classmethod
    def by_name(cls, session, name):
        """Get a group from a given name."""
        return cls.first(session, where=(cls.name == name,))


user__group = Table('user__group', Base.metadata,
                    Column('group_id', Integer, ForeignKey('group.id')),
                    Column('user_id', Integer, ForeignKey('user.id'))
                    )


class Countries(Base):
    """Describe allowed countries for user."""

    name = Column(Unicode(255), nullable=False)

    @classmethod
    def by_name(cls, session, name):
        """Get a country from a given name."""
        return cls.first(session, where=(cls.name == name,))


class User(Base):
    """
    Describe a user.

    This model handle users granted to access pyvac.
    """

    login = Column(Unicode(255), nullable=False)
    _password = Column('password', Unicode(60), nullable=True)

    firstname = Column(Unicode(255), nullable=True)
    lastname = Column(Unicode(255), nullable=True)
    email = Column(Unicode(255), nullable=True)
    groups = relationship(Group, secondary=user__group, lazy='joined',
                          backref='users')

    role = Column(Enum('user', 'manager', 'admin', name='enum_user_role'),
                  nullable=False,
                  default='user')

    manager_id = Column(Integer, ForeignKey(u'user.id'))
    manager = relationship(u'User', remote_side=u'User.id', backref=u'users')
    manager_dn = Column(Unicode(255), nullable=False, default=u'')

    ldap_user = Column(Boolean, nullable=False, default=False)
    dn = Column(Unicode(255), nullable=False, default=u'')

    country_id = Column('country_id', ForeignKey(Countries.id))
    _country = relationship(Countries, backref='users')

    ou = Column(Unicode(255), nullable=True)
    uid = Column(Unicode(255), nullable=True)

    firm = ''
    feature_flags = {}

    @property
    def name(self):
        """Internal helper to retrieve user name."""
        return u'%s %s' % (self.firstname.capitalize(),
                           self.lastname.capitalize())\
            if self.firstname and self.lastname else self.login

    def _get_password(self):
        return self._password

    def _set_password(self, password):
        self._password = unicode(crypt.encode(password))

    password = property(_get_password, _set_password)
    password = synonym('_password', descriptor=password)

    @property
    def is_super(self):
        """Check if user has rights to manage other users."""
        return self.role in ('admin', 'manager')

    @property
    def is_admin(self):
        """Check if user has admin rights."""
        return self.role in ('admin',)

    @property
    def is_manager(self):
        """Check if user has admin rights."""
        return self.role in ('manager',)

    def is_sudoer(self, session):
        """Check if user has sudoer rights."""
        return Group.by_name(session, 'sudoer') in self.groups

    @property
    def has_no_role(self):
        """Check if user has no specific rights."""
        return self.role in ('user',)

    @property
    def nickname(self):
        """Return user nickname."""
        return self.uid.lower() if self.uid else ''

    @property
    def manager_mail(self):
        """Get manager email for a user."""
        if not self.ldap_user:
            return self.manager.email
        else:
            ldap = LdapCache()
            user_data = ldap.search_user_by_dn(self.manager_dn)
            return user_data['email']

    @property
    def manager_name(self):
        """Get manager name for a user."""
        if not self.ldap_user:
            return self.manager.name
        else:
            ldap = LdapCache()
            user_data = ldap.search_user_by_dn(self.manager_dn)
            return user_data['login']

    @property
    def arrival_date(self):
        """Get arrival date in the company for a user."""
        if not self.ldap_user:
            return

        ldap = LdapCache()
        try:
            user_data = ldap.search_user_by_dn(self.dn)
            return user_data['arrivalDate']
        except:
            pass

    @property
    def seniority(self):
        """Return how many years the user has been employed."""
        arrival_date = self.arrival_date
        if not arrival_date:
            return 0

        today = datetime.now()
        nb_year = today.year - arrival_date.year
        current_arrival_date = arrival_date.replace(year=today.year)
        if today < current_arrival_date:
            nb_year = nb_year - 1

        return nb_year

    @property
    def anniversary(self):
        """Return how many days left until next anniversary."""
        arrival_date = self.arrival_date
        if not arrival_date:
            return (False, 0)

        today = datetime.now()
        current_arrival_date = arrival_date.replace(year=today.year)
        # if it's already past for this year
        if current_arrival_date < today:
            current_arrival_date += relativedelta(months=12)
        delta = (today - current_arrival_date).days

        return (True if delta == 0 else False, abs(delta))

    @classmethod
    def by_login(cls, session, login):
        """Get a user from a given login."""
        user = cls.first(session,
                         where=((cls.login == login),)
                         )
        # XXX it's appear that this is not case sensitive !
        return user if user and user.login == login else None

    @classmethod
    def by_email(cls, session, email):
        """Get a user from a given email."""
        user = cls.first(session,
                         where=((cls.email == email),)
                         )
        # XXX it's appear that this is not case sensitive !
        return user if user and user.email == email else None

    @classmethod
    def by_credentials(cls, session, login, password, ldap=False):
        """Get a user from given credentials."""
        if ldap:
            try:
                return cls.by_ldap_credentials(session, login, password)
            except Exception:
                return None
        else:
            user = cls.by_login(session, login)
            if not user:
                return None
            if crypt.check(user.password, password):
                return user

    def validate(self, session, ldap=False):
        """Validate that the current user can be saved.

        If ldap is active, do not handle passwords.
        """
        errors = []
        if not self.login:
            errors.append(u'login is required')
        else:
            other = User.by_login(session, self.login)
            if other and other.id != self.id:
                errors.append(u'duplicate login %s' % self.login)
        # no need for password for ldap users
        if not ldap and not self.password:
            errors.append(u'password is required')
        if not self.email:
            errors.append(u'email is required')
        elif not re_email.match(self.email):
            errors.append(u'%s is not a valid email' % self.email)

        if len(errors):
            raise ModelError(errors)
        return True

    @classmethod
    def by_role(cls, session, role):
        """Get a user from a given role."""
        return cls.find(session, where=((cls.role == role),))

    @classmethod
    def by_country(cls, session, country_id):
        """Get users for a given country."""
        return cls.find(session, where=((cls.country_id == country_id),))

    @classmethod
    def get_admin_by_country(cls, session, country):
        """Get user with role admin for a specific country."""
        return cls.first(session,
                         join=(cls._country),
                         where=(Countries.name == country,
                                cls.role == 'admin'),
                         order_by=cls.id)

    @classmethod
    def by_dn(cls, session, user_dn):
        """Get a user using ldap user dn."""
        user = cls.first(session,
                         where=((cls.dn == user_dn),)
                         )
        # XXX it's appear that this is not case sensitive !
        return user if user and user.dn == user_dn else None

    @classmethod
    def by_ldap_credentials(cls, session, login, password):
        """Get a user using ldap credentials."""
        ldap = LdapCache()
        user_data = ldap.authenticate(login, password)
        if user_data is not None:
            login = unicode(user_data['login'])
            user = User.by_login(session, login)
            # check what type of user it is
            group = u'user'
            # if it's a manager members should have him associated as such
            what = '(manager=%s)' % user_data['dn']
            if len(ldap._search(what, None)) > 0:
                group = u'manager'
            # if it's an admin he should be in admin group
            what = '(member=%s)' % user_data['dn']
            if len(ldap._search_admin(what, None)) > 0:
                group = u'admin'
            log.info('group found for %s: %s' % (login, group))
            # create user if needed
            if not user:
                user = User.create_from_ldap(session, user_data, group)
            else:
                # update user with ldap informations in case it changed
                user.email = user_data['email'].decode('utf-8')
                user.firstname = user_data['firstname'].decode('utf-8')
                user.lastname = user_data['lastname'].decode('utf-8')
                user.manager_dn = user_data['manager_dn'].decode('utf-8')
                user.dn = user_data['dn'].decode('utf-8')
                user.role = group
                if 'ou' in user_data:
                    user.ou = user_data['ou'].decode('utf-8')
                if 'uid' in user_data:
                    user.uid = user_data['uid'].decode('utf-8')

                # handle update of groups if it has changed
                exists = []
                group_ids = [Group.by_name(session, group).id]

                for ugroup in user.groups:
                    exists.append(ugroup.id)
                    if ugroup.id not in group_ids:
                        # keep sudoer group info
                        if ugroup.name != 'sudoer':
                            user.groups.remove(ugroup)

                for group_id in group_ids:
                    if group_id not in exists:
                        user.groups.append(Group.by_id(session, group_id))

            return user

    @classmethod
    def create_from_ldap(cls, session, data, group):
        """Create a new user in database using ldap data information."""
        country = Countries.by_name(session, data['country'].decode('utf-8'))

        user = User(login=data['login'].decode('utf-8'),
                    email=data['email'].decode('utf-8'),
                    firstname=data['firstname'].decode('utf-8'),
                    lastname=data['lastname'].decode('utf-8'),
                    _country=country,
                    manager_dn=data['manager_dn'].decode('utf-8'),
                    ldap_user=True,
                    dn=data['dn'].decode('utf-8'),
                    role=group,
                    )
        ou = data['ou'].decode('utf-8') if 'ou' in data else None
        if ou:
            user.ou = ou
        uid = data['uid'].decode('utf-8') if 'uid' in data else None
        if uid:
            user.uid = uid
        # put in correct group
        user.groups.append(Group.by_name(session, group))
        session.add(user)
        session.flush()

        return user

    @classmethod
    def sync_ldap_info(cls, session):
        """Resynchronize ldap information in database.

        for changes in role/units.
        """
        ldap = LdapCache()
        managers = ldap.list_manager()
        admins = ldap.list_admin()
        for user in User.find(session, order_by=[User.dn]):
            group = u'user'
            # if it's a manager members should have him associated as such
            if user.dn in managers:
                group = u'manager'
            # if it's an admin he should be in admin group
            if user.dn in admins:
                group = u'admin'

            user.role = group
            # handle update of groups if it has changed
            exists = []
            group_ids = [Group.by_name(session, group).id]

            for ugroup in user.groups:
                exists.append(ugroup.id)
                if ugroup.id not in group_ids:
                    # keep sudoer group info
                    if ugroup.name != 'sudoer':
                        user.groups.remove(ugroup)

            for group_id in group_ids:
                if group_id not in exists:
                    user.groups.append(Group.by_id(session, group_id))

    def get_admin(self, session):
        """Get admin for country of user."""
        if not self.ldap_user:
            return self.get_admin_by_country(session, self.country)
        else:
            # retrieve from ldap
            ldap = LdapCache()
            return ldap.get_hr_by_country(self.country)

    @property
    def country(self):
        """Get name of associated country."""
        return self._country.name

    @classmethod
    def get_all_nicknames(cls, session):
        """Retrieve all distinct available nicknames (uid field)."""
        return [nick[0]
                for nick in session.query(User.uid).distinct().all()
                if nick[0]]

    @classmethod
    def for_admin(cls, session, admin):
        """Get all users for an admin regarding his country."""
        return cls.find(session,
                        where=(cls.country_id == admin.country_id,
                               cls.id != admin.id,
                               cls.ldap_user == admin.ldap_user,
                               ),
                        order_by=cls.lastname)

    @classmethod
    def managed_users(cls, session, manager):
        """Get all users for a manager without regarding his country."""
        return cls.find(session,
                        where=(cls.id != manager.id,
                               cls.ldap_user == manager.ldap_user,
                               cls.manager_dn == manager.dn,
                               ),
                        order_by=cls.lastname)

    @classmethod
    def load_feature_flags(cls, filename):
        """Load features flag per users."""
        try:
            with open(filename) as fdesc:
                conf = yaml.load(fdesc, YAMLLoader)
            cls.feature_flags = conf.get('users_flags', {})
            log.info('Loaded users feature flags file %s: %s' %
                     (filename, cls.feature_flags))
        except IOError:
            log.warn('Cannot load users feature flags file %s' % filename)

    def has_feature(self, feature):
        """Check if user has a feature enabled."""
        return feature in self.feature_flags.get(self.login, [])

    def get_rtt_taken_year(self, session, year):
        """Retrieve taken RTT for a user for current year."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        return sum([req.days for req in self.requests
                    if (req.vacation_type.name == u'RTT') and
                    (req.status in valid_status) and
                    (req.date_from.year == year)])

    def get_rtt_usage(self, session):
        """Get RTT usage for a user."""
        kwargs = {'name': u'RTT',
                  'country': self.country,
                  'user': self,
                  'session': session}
        vac = VacationType.by_name_country(**kwargs)
        if not vac:
            return
        allowed = vac.acquired(**kwargs)
        if allowed is None:
            return

        current_year = datetime.now().year
        taken = self.get_rtt_taken_year(session, current_year)

        left = allowed - taken
        if left >= 10 or left < 0:
            state = 'error'
        elif left >= 5:
            state = 'warning'
        else:
            state = 'success'

        ret = {'allowed': allowed, 'taken': taken, 'left': left,
               'year': current_year, 'state': state}
        return ret

    @classmethod
    def get_rtt_acquired_history(cls, session, user, year):
        """Get RTT acquired history."""
        kwargs = {'name': u'RTT',
                  'country': user.country,
                  'user': user,
                  'session': session,
                  'year': year,
                  'dt': True}
        vac = VacationType.by_name_country(**kwargs)
        if not vac:
            return
        acquired = vac.acquired(**kwargs)
        if not acquired:
            return

        return [{'date': item, 'value': 1} for item in acquired]

    @classmethod
    def get_rtt_taken_history(cls, session, user, year):
        """Get RTT taken history."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        entries = [req for req in user.requests
                   if (req.vacation_type.name == u'RTT') and
                   (req.status in valid_status) and
                   (req.date_from.year == year)]

        return [{'date': req.date_from, 'value': -req.days} for req in entries]

    @classmethod
    def get_rtt_history(cls, session, user, year):
        """Get RTT history for given user: taken + acquired, sorted by date."""
        acquired = cls.get_rtt_acquired_history(session, user, year)
        if acquired is None:
            return []
        taken = cls.get_rtt_taken_history(session, user, year)

        history = sorted(acquired + taken)

        return history

    @classmethod
    def get_cp_acquired_history(cls, vac, acquired, today=None):
        """Get CP acquired history."""
        today = today or datetime.now()
        cycle_start, _ = vac.get_cycle_boundaries(today)

        cycle_start, _ = vac.get_cycle_boundaries(today)
        if cycle_start < vac.epoch:
            cycle_start = vac.epoch

        delta = relativedelta(cycle_start, today)
        months = abs(delta.months)

        return [{'date': cycle_start + relativedelta(months=idx),
                 'value': vac.coeff}
                for idx, item in enumerate(xrange(months + 1))]

    @classmethod
    def get_cp_restant_history(cls, vac, session, user, today=None):
        """Get CP restant history."""
        today = today or datetime.now()
        cycle_start, cycle_end = vac.get_cycle_boundaries(today)

        cycle_start, _ = vac.get_cycle_boundaries(today)
        if cycle_start < vac.epoch:
            cycle_start = vac.epoch

        thresholds = [cycle_start, cycle_end]

        def get_restant(date):
            data = vac.acquired(user, date, session)
            return data['restant'] + data.get('n_1', 0)

        ret = {}
        for date in thresholds:
            ret[date] = get_restant(date)
        return ret

    @classmethod
    def get_cp_taken_history(cls, session, user, date):
        """Get CP taken history."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        entries = [req for req in user.requests
                   if (req.vacation_type.name == u'CP') and
                   (req.status in valid_status) and
                   (req.date_from >= date)]

        # set taken to 12h hour so sorted history correctly put the acquired
        # before the taken
        return [{'date': req.date_from.replace(hour=12),
                 'value': -req.days} for req in entries]

    def get_cp_taken_year(self, session, date):
        """Retrieve taken CP for a user for current year."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        return sum([req.days for req in self.requests
                    if (req.vacation_type.name == u'CP') and
                    (req.status in valid_status) and
                    (req.date_from >= date)])

    def get_cp_taken_cycle(self, session, date_start, date_end):
        """Retrieve taken CP for a user for current cycle."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        return sum([req.days for req in self.requests
                    if (req.vacation_type.name == u'CP') and
                    (req.status in valid_status) and
                    (req.date_from >= date_start) and
                    (req.date_to <= date_end)])

    @classmethod
    def get_cp_history(cls, session, user, year):
        """Get CP history for given user: taken + acquired, sorted by date."""
        today = datetime.now().replace(year=year)
        kwargs = {'session': session,
                  'name': u'CP',
                  'country': user.country,
                  'user': user,
                  'today': today}
        vac = VacationType.by_name_country(**kwargs)
        if not vac:
            return [], []
        if today < vac.epoch:
            return [], []
        allowed = vac.acquired(**kwargs)
        if not allowed:
            return [], []

        cycle_start, _ = vac.get_cycle_boundaries(today)
        if cycle_start < vac.epoch:
            cycle_start = vac.epoch

        raw_restant = cls.get_cp_restant_history(vac, session, user, today)
        raw_acquired = cls.get_cp_acquired_history(vac, allowed, today)
        acquired = []
        total = 0
        for item in raw_acquired:
            if item['date'] < cycle_start:
                total += item['value']
            else:
                if total:
                    item['value'] = total
                    total = 0
                acquired.append(item)
        taken = cls.get_cp_taken_history(session, user, cycle_start)

        history = sorted(acquired + taken)

        def get_restant_val(date):
            value = raw_restant.get(date)
            if not value:
                for item in raw_restant:
                    if item > date:
                        value = raw_restant[item]
                        break
            return value

        restant = dict([(entry['date'], get_restant_val(entry['date']))
                        for entry in history])

        return history, restant

    def get_cp_usage(self, session, today=None):
        """Get CP usage for a user."""
        kwargs = {'session': session,
                  'name': u'CP',
                  'country': self.country,
                  'user': self,
                  'today': today}
        vac = VacationType.by_name_country(**kwargs)
        if not vac:
            return
        allowed = vac.acquired(**kwargs)
        if not allowed:
            return

        cycle_start = allowed['cycle_start']
        cycle_end = allowed['cycle_end']
        taken = self.get_cp_taken_cycle(session, cycle_start, cycle_end)
        log.debug('taken %d for %s -> %s' % (taken, cycle_start, cycle_end))

        return vac.get_left(taken, allowed)

    def get_cp_class(self, session):
        kwargs = {'session': session,
                  'name': u'CP',
                  'country': self.country,
                  'user': self}
        vac = VacationType.by_name_country(**kwargs)
        return vac


vacation_type__country = Table('vacation_type__country', Base.metadata,
                               Column('vacation_type_id', Integer,
                                      ForeignKey('vacation_type.id')),
                               Column('country_id', Integer,
                                      ForeignKey('countries.id'))
                               )


class BaseVacation(object):
    """Base class to use to customize Vacation type behavior."""

    name = None

    @classmethod
    def acquired(cls, **kwargs):
        """Return acquired vacation this year to current day."""
        raise NotImplementedError

    @classmethod
    def get_left(cls, taken, allowed):
        """Return how much vacation is left after taken has been accounted."""
        raise NotImplementedError

    @classmethod
    def validate_request(cls, user, pool, days, date_from, date_to):
        """Validate request for user for this vacation type."""
        raise NotImplementedError

    @classmethod
    def convert_days(cls, days):
        return days


class RTTVacation(BaseVacation):
    """Implement RTT vacation behavior."""

    name = u'RTT'
    country = u'fr'
    except_months = []

    @classmethod
    def initialize(cls, except_months):
        cls.except_months = [int(month) for month in except_months]
        log.info('Initialize except_months for RTT vacation: %s ' %
                 cls.except_months)

    @classmethod
    def acquired(cls, **kwargs):
        """Return acquired vacation this year to current day.

        We acquire one RTT at the start of each month except in august and
        december.
        """
        start_month = 1
        today = datetime.now()

        # if we provided a year, this means we want to force the year to use
        year = kwargs.get('year')
        if year and year != today.year:
            # go back to the end of the given year
            today = datetime(year, 12, 1)

        user = kwargs.get('user')
        if user and (user.created_at.year == today.year):
            start_month = user.created_at.month

        use_dt = kwargs.get('dt')
        if use_dt:
            # we want to return datetimes
            return [datetime(today.year, i, 1)
                    for i in xrange(start_month, today.month + 1)
                    if i not in cls.except_months]

        return len([i for i in xrange(start_month, today.month + 1)
                    if i not in cls.except_months])


class CPVacation(BaseVacation):
    """Implement CP vacation behavior."""

    name = u'CP'
    country = u'fr'
    epoch = datetime(2015, 6, 1)
    coeff = 2.08  # per month
    users_base = {}

    @classmethod
    def initialize(cls, filename):
        try:
            with open(filename) as fdesc:
                conf = yaml.load(fdesc, YAMLLoader)
            cls.users_base = conf.get('users_base')
            base_date = conf.get('date')
            base_date = datetime.strptime(base_date, '%d/%m/%Y')
            cls.epoch = base_date
            log.info('Loaded user base file %s for CP vacation' % filename)
        except IOError:
            log.warn('Cannot load user base file %s for CP vacation' %
                     filename)

    @classmethod
    def get_left(cls, taken, allowed):
        """Return how much vacation is left after taken has been accounted."""
        cycle_end = allowed['cycle_end']
        restant = allowed['restant']
        n_1 = allowed['n_1']
        acquis = allowed['acquis']

        left_n_1, left_restant, left_acquis = cls.consume(taken, n_1,
                                                          restant,
                                                          acquis)

        # must handle 3 pools: acquis, restant, and N-1
        ret_n_1 = {
            'allowed': allowed['n_1'],
            'left': left_n_1,
            'expire': cycle_end - relativedelta(months=5)}
        ret_acquis = {
            'allowed': allowed['acquis'],
            'left': left_acquis,
            'expire': cycle_end.replace(year=cycle_end.year + 1)}
        ret_restant = {
            'allowed': allowed['restant'],
            'left': left_restant,
            'expire': allowed['cycle_end']}
        return {'acquis': ret_acquis, 'restant': ret_restant,
                'n_1': ret_n_1,
                'taken': taken}

    @classmethod
    def consume(cls, taken, n_1, restant, acquis):
        """Remove taken CP from N-1 pool then Restant pool then Acquis pool."""
        exceed = 0
        if n_1 < 0:
            restant = restant + n_1
            left_n_1 = 0
            n_1 = 0

        left_n_1 = n_1 - abs(taken)
        if left_n_1 < 0:
            exceed = abs(left_n_1)
            left_n_1 = 0

        left_restant = restant - exceed
        if left_restant < 0:
            exceed = abs(left_restant)
            left_restant = 0
            left_acquis = acquis - exceed
        else:
            left_acquis = acquis

        return left_n_1, left_restant, left_acquis

    @classmethod
    def get_cycle_boundaries(cls, date, raising=None):
        """Retrieve cycle start and end date for given date.

        Will raise an exception if raising parameter is passed,
        this is useful for stopping recursion calls.
        """
        if date >= datetime(date.year, 6, 1):
            start = datetime(date.year, 5, 31)
            end = datetime(date.year + 1, 5, 31)
        else:
            start = datetime(date.year - 1, 5, 31)
            end = datetime(date.year, 5, 31)

        if raising and ((start < cls.epoch) or (end < cls.epoch)):
            raise FirstCycleException()

        return start, end

    @classmethod
    def get_acquis(cls, user, starting_date, today=None):
        """."""
        today = today or datetime.now()

        delta = relativedelta(starting_date, today)
        months = abs(delta.months)
        years = abs(delta.years)

        acquis = None
        cp_bonus = 0
        # add bonus CP based on arrival_date, 1 more per year each 5 years
        # cp bonus are added on the last acquisition day of previous cycle,
        # so on 31/05 of year - 1
        if years > 0:
            cp_bonus = int(math.floor(user.seniority / 5))

        if not months and years:
            months = 12
            acquis = 25 + cp_bonus

        log.debug('%s: using coeff %s * months %s + (bonus %s)' %
                  (user.login, cls.coeff, months, cp_bonus))
        acquis = acquis or (months * cls.coeff)
        return acquis

    @classmethod
    def acquired(cls, user, today=None, session=None, **kwargs):
        """Return acquired vacation this year to current day.

        We acquire a base of 25 CP per year.
        A year period is not a normal year but from 31/05/year to 31/05/year+1
        We call that a cycle.

        CP values exists in 2 pools: restant and acquis.
        restant = acquis from previous cycle, except for first cycle
        where we retrieve them in a file if available otherwise we start
        with restant = 0

        WORKFLOW
        - retrieve current cycle boundaries
        - retrieve previous cycle boundaries
        - if previous cycle is available (i.e we are not in the first cycle)
        - retrieve amount of restant/acquis from previous cycle
        - use acquis from previous cycle for restant of current one
        """

        # if user is not in france, discard
        if user.country not in ('fr'):
            log.info('user %s not in country fr, discarding' % user.login)
            return

        # if user has no arrival_date, discard
        if not user.arrival_date:
            log.info('user %s has no arrival_date, discarding' % user.login)
            return

        today = today or datetime.now()
        # if user is not yet active, discard
        if user.arrival_date > today:
            log.info('user %s is not yet active, discarding' % user.login)
            return

        n_1 = 0
        restant = 0
        try:
            start, end = cls.get_cycle_boundaries(today, raising=True)
            # use user arrival_date if after starting cycle date
            if user.arrival_date > start:
                start = user.arrival_date
            acquis = cls.get_acquis(user, start, today)
            previous_usage = user.get_cp_usage(session, today=start)
            taken = user.get_cp_taken_cycle(session, start, end)
            # add taken value as it is already consumed by get_cp_usage method
            # so we don't consume it twice.
            restant = previous_usage['acquis']['left'] + taken

        except FirstCycleException:
            # cannot go back before first cycle, so use current cycle values
            start, end = cls.get_cycle_boundaries(today)
            # use user arrival_date if after starting cycle date
            if user.arrival_date > start:
                start = user.arrival_date
            acquis = cls.get_acquis(user, start, today)
            epoch_restants = cls.users_base.get(user.login,
                                                {'restants': 0, 'n_1': 0})
            # add seniority CP bonus for the 1st cycle
            cp_bonus = int(math.floor(user.seniority / 5))
            restant = epoch_restants['restants'] + cp_bonus
            n_1 = epoch_restants['n_1']
            start = cls.epoch

        return {'acquis': acquis, 'restant': restant,
                'n_1': n_1,
                'cycle_start': start, 'cycle_end': end}

    @classmethod
    def validate_request(cls, user, pool, days, date_from, date_to):
        """Validate request regarding user pool."""
        # check that we request vacations in the allowed cycle
        if pool is not None and (
                not (date_from <= date_to <=
                     pool['acquis']['expire'])):
            msg = ('CP can only be used until %s.' %
                   pool['acquis']['expire'].strftime('%d/%m/%Y'))
            return msg


class CPLUVacation(BaseVacation):
    """Implement CP vacation behavior for Luxembourg."""

    name = u'CP'
    country = u'lu'
    epoch = datetime(2016, 1, 1)
    coeff = 2.083 * 8  # per month 16.664 hours
    users_base = {}

    @classmethod
    def initialize(cls, filename):
        try:
            with open(filename) as fdesc:
                conf = yaml.load(fdesc, YAMLLoader)
            cls.users_base = conf.get('users_base')
            base_date = conf.get('date')
            base_date = datetime.strptime(base_date, '%d/%m/%Y')
            cls.epoch = base_date
            log.info('Loaded user base file %s for CP vacation' % filename)
        except IOError:
            log.warn('Cannot load user base file %s for CP vacation' %
                     filename)

    @classmethod
    def get_left(cls, taken, allowed):
        """Return how much vacation is left after taken has been accounted."""
        cycle_end = allowed['cycle_end']
        restant = allowed['restant']
        acquis = allowed['acquis']

        # add CP to be recovered if a passed holiday was a Saturday or Sunday
        recovered_cp = get_lu_recovered_holiday(allowed['cycle_start'].year,
                                                allowed['cycle_start'].date(),
                                                datetime.now().date())
        acquis = acquis + cls.convert_days(recovered_cp)

        left_restant, left_acquis = cls.consume(taken, restant, acquis)

        # must handle 2 pools: acquis, restant
        ret_acquis = {
            'allowed': allowed['acquis'],
            'left': left_acquis,
            'expire': cycle_end.replace(year=cycle_end.year)}
        ret_restant = {
            'allowed': allowed['restant'],
            'left': left_restant,
            # add 3 months here
            'expire': allowed['cycle_end'].replace(year=cycle_end.year - 1) + relativedelta(months=3)} # noqa
        return {'acquis': ret_acquis, 'restant': ret_restant,
                'taken': taken}

    @classmethod
    def consume(cls, taken, restant, acquis):
        """First remove taken CP from Restant pool then from Acquis pool."""
        exceed = 0
        left_restant = restant - abs(taken)
        if left_restant < 0:
            exceed = abs(left_restant)
            left_restant = 0
        left_acquis = acquis - exceed
        return left_restant, left_acquis

    @classmethod
    def get_cycle_boundaries(cls, date, raising=None):
        """Retrieve cycle start and end date for given date.

        Will raise an exception if raising parameter is passed,
        this is useful for stopping recursion calls.
        """
        start = datetime(date.year, 1, 1)
        end = datetime(date.year, 12, 31)

        if raising and ((start < cls.epoch) or (end < cls.epoch)):
            raise FirstCycleException()

        return start, end

    @classmethod
    def get_acquis(cls, user, starting_date, today=None):
        """."""
        today = today or datetime.now()

        delta = relativedelta(starting_date, today)
        months = abs(delta.months)
        years = abs(delta.years)

        acquis = None
        cp_bonus = 0
        # add bonus CP based on arrival_date, 1 more per year each 5 years
        # cp bonus are added on the last acquisition day of previous cycle,
        # so on 31/05 of year - 1
        if years > 0:
            cp_bonus = int(math.floor(user.seniority / 5))

        if not months and years:
            months = 12
            acquis = 25 + cp_bonus

        log.debug('%s: using coeff %s * months %s + (bonus %s)' %
                  (user.login, cls.coeff, months, cp_bonus))
        acquis = acquis or (months * cls.coeff)
        return acquis

    @classmethod
    def acquired(cls, user, today=None, session=None, **kwargs):
        """Return acquired vacation this year to current day.

        We acquire a base of 200 hours per year.
        A year period is a normal year, we call that a cycle.

        WORKFLOW
        - retrieve current cycle boundaries
        - retrieve previous cycle boundaries
        - if previous cycle is available (i.e we are not in the first cycle)
        - retrieve amount of CP from previous cycle
        """

        # if user is not in luxembourg, discard
        if user.country not in ('lu'):
            log.info('user %s not in country lu, discarding' % user.login)
            return

        # if user has no arrival_date, discard
        if not user.arrival_date:
            log.info('user %s has no arrival_date, discarding' % user.login)
            return

        today = today or datetime.now()
        # if user is not yet active, discard
        if user.arrival_date > today:
            log.info('user %s is not yet active, discarding' % user.login)
            return

        restant = 0
        try:
            start, end = cls.get_cycle_boundaries(today, raising=True)
            # use user arrival_date if after starting cycle date
            if user.arrival_date > start:
                start = user.arrival_date
            acquis = 200
            dt = start - relativedelta(days=1)
            taken = user.get_cp_taken_cycle(session, start, end)
            previous_usage = user.get_cp_usage(session, today=dt)
            if not previous_usage:
                left_acquis = 0
            else:
                left_acquis = previous_usage['acquis']['left']
                # previous acquis are only valid 3 months
                if today > previous_usage['acquis']['expire'] + relativedelta(months=3): # noqa
                    left_acquis = 0
            # add taken value as it is already consumed by get_cp_usage method
            # so we don't consume it twice.
            restant = left_acquis + taken
        except FirstCycleException:
            # cannot go back before first cycle, so use current cycle values
            start, end = cls.get_cycle_boundaries(today)
            start = cls.epoch
            # use user arrival_date if after starting cycle date
            if user.arrival_date > start:
                start = user.arrival_date
            acquis = cls.users_base.get(user.login, 200)
            start = cls.epoch

        return {'acquis': acquis, 'restant': restant,
                'cycle_start': start, 'cycle_end': end}

    @classmethod
    def validate_request(cls, user, pool, days, date_from, date_to):
        """Validate request regarding user pool."""
        if pool is not None:
            total_left = (pool['acquis']['left'] +
                          pool['restant']['left'])

        if pool is not None and total_left <= 0:
            msg = 'No CP left to take.'
            return msg

        # check that we have enough CP to take
        if pool is not None and days > total_left:
            msg = 'You only have %d CP to use.' % total_left
            return msg

        # check that we request vacations in the allowed cycle
        if pool is not None and (
                not (date_from <= date_to <=
                     pool['acquis']['expire'])):
            msg = ('CP can only be used until %s.' %
                   pool['acquis']['expire'].strftime('%d/%m/%Y'))
            return msg

        # check that the user has at least 3 months of seniority
        if user.arrival_date:
            today = datetime.now()
            delta = today - user.arrival_date
            if delta.days < (3 * 31):
                msg = 'You need 3 months of seniority before using your CP'
                return msg

    @classmethod
    def convert_days(cls, days):
        """Return value in hours"""
        return days * 8


class VacationType(Base):
    """Describe allowed type of vacation to request."""

    name = Column(Unicode(255), nullable=False)
    visibility = Column(Unicode(255), nullable=True)

    countries = relationship(Countries, secondary=vacation_type__country,
                             lazy='joined', backref='vacation_type')

    _vacation_classes = {}

    # save internal map of loaded module classes
    for subclass in BaseVacation.__subclasses__():
        _vac_id = '%s_%s' % (subclass.name, subclass.country)
        _vacation_classes[_vac_id] = subclass

    @classmethod
    def by_name(cls, session, name):
        """Get a vacation type from a given name."""
        return cls.first(session, where=(cls.name == name,))

    @classmethod
    def by_country(cls, session, country):
        """Get vacation type from a given country."""
        ctry = Countries.by_name(session, country)
        return cls.find(session, where=(cls.countries.contains(ctry),),
                        order_by=cls.id)

    @classmethod
    def by_name_country(cls, session, name, country, user=None, **kwargs):
        """Return allowed count of vacations per name and country."""
        ctry = Countries.by_name(session, country)
        vac = cls.first(session, where=(cls.countries.contains(ctry),
                                        cls.name == name), order_by=cls.id)

        if not vac:
            return

        vacation_name = '%s_%s' % (vac.name, country)
        return cls._vacation_classes.get(vacation_name)


class Request(Base):
    """Describe a user request for vacation."""

    date_from = Column(DateTime, nullable=False)
    date_to = Column(DateTime, nullable=False)
    days = Column(Float(precision=1), nullable=False)

    date_updated = Column(DateTime, default=func.now(), onupdate=func.now())

    vacation_type_id = Column('vacation_type_id', ForeignKey(VacationType.id),
                              nullable=False)
    vacation_type = relationship(VacationType, backref='requests')

    status = Column(Enum('PENDING',
                         'ACCEPTED_MANAGER',
                         'DENIED',
                         'APPROVED_ADMIN',
                         'CANCELED',
                         'ERROR',
                    name='enum_request_status'),
                    nullable=False, default='PENDING')
    # why this request
    message = Column(UnicodeText())
    # reason of cancel or deny
    reason = Column(UnicodeText())
    # for future use
    label = Column(UnicodeText())
    # in case of ERROR to store the error message
    error_message = Column(UnicodeText())
    # actor who performed last action on request
    last_action_user_id = Column(Integer, nullable=True)
    # store caldav ics url
    ics_url = Column(UnicodeText())
    # vacation_type pool counters when the action has been made
    pool_status = Column(UnicodeText())

    notified = Column(Boolean, default=False)
    user_id = Column('user_id', ForeignKey(User.id))
    user = relationship(User, backref='requests')

    sender_mail = ''

    def update_status(self, status):
        """Reset notified flag when changing status."""
        self.status = status
        self.notified = False

    def flag_error(self, message):
        """Set request in ERROR and assign message."""
        self.status = 'ERROR'
        self.error_message = message

    @classmethod
    def by_manager(cls, session, manager, count=None):
        """Get requests for users under given manager."""
        if manager.ldap_user:
            return cls.by_manager_ldap(session, manager, count=count)
        # we only want to display less than 3 months data
        date_limit = datetime.now() - timedelta(days=90)
        return cls.find(session,
                        join=(cls.user),
                        where=(User.manager_id == manager.id,
                               cls.status != 'CANCELED',
                               cls.date_from >= date_limit,),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def by_manager_ldap(cls, session, manager, count=None):
        """Get requests for users under given manager."""
        # we only want to display less than 3 months data
        date_limit = datetime.now() - timedelta(days=90)
        return cls.find(session,
                        join=(cls.user),
                        where=(User.manager_dn == manager.dn,
                               cls.status != 'CANCELED',
                               cls.date_from >= date_limit,),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def by_user(cls, session, user, count=None):
        """Get requests for given user."""
        # we only want to display less than 1 year data
        date_limit = datetime.now() - timedelta(days=366)
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status != 'CANCELED',
                               cls.date_from >= date_limit,),
                        count=count,
                        order_by=(cls.user_id, cls.date_from.desc()))

    @classmethod
    def by_user_future(cls, session, user, count=None):
        """Get requests for given user in the future."""
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status != 'CANCELED',
                               cls.status != 'DENIED',
                               cls.status != 'ERROR',
                               cls.date_from >= datetime.now(),),
                        count=count,
                        order_by=(cls.user_id, cls.date_from.desc()))

    @classmethod
    def by_user_future_pending(cls, session, user, count=None):
        """Get pending requests for given user in the future.

        retrieve status = PENDING, ACCEPTED_MANAGER
        """
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               or_(cls.status == 'PENDING',
                                   cls.status == 'ACCEPTED_MANAGER'),
                               cls.date_from >= datetime.now(),),
                        count=count,
                        order_by=(cls.user_id, cls.date_from.desc()))

    @classmethod
    def by_user_future_approved(cls, session, user, count=None):
        """Get pending requests for given user in the future.

        retrieve status = APPROVED_ADMIN
        """
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status == 'APPROVED_ADMIN',
                               cls.date_from >= datetime.now(),),
                        count=count,
                        order_by=(cls.user_id, cls.date_from.desc()))

    @classmethod
    def by_status(cls, session, status, count=None, notified=False):
        """Get requests for given status."""
        return cls.find(session,
                        where=(cls.status == status,
                               cls.notified == notified),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def all_for_admin(cls, session, count=None):
        """Get all requests manageable by admin."""
        # we only want to display less than 3 months data
        date_limit = datetime.now() - timedelta(days=90)
        return cls.find(session,
                        where=(cls.status != 'CANCELED',
                               cls.date_from >= date_limit,),
                        count=count,
                        order_by=cls.user_id,
                        eagerload=['user'])

    @classmethod
    def all_for_admin_per_country(cls, session, country, count=None):
        """Get all requests manageable by admin per country."""
        country_id = Countries.by_name(session, country).id
        # we only want to display less than 3 months data
        date_limit = datetime.now() - timedelta(days=90)
        return cls.find(session,
                        join=(cls.user),
                        where=(cls.status != 'CANCELED',
                               User.country_id == country_id,
                               cls.date_from >= date_limit,
                               ),
                        count=count,
                        order_by=cls.user_id,
                        eagerload=['user'])

    @classmethod
    def in_conflict_manager(cls, session, req, count=None):
        """Get all requests conflicting on given request dates.

        with common user manager.
        """
        return cls.find(session,
                        join=(cls.user),
                        where=(or_(and_(cls.date_from >= req.date_from,
                                        cls.date_to <= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_from),
                               and_(cls.date_from <= req.date_to,
                                    cls.date_to >= req.date_from)),
                               cls.status != 'CANCELED',
                               cls.status != 'DENIED',
                               User.manager_dn == req.user.manager_dn,
                               cls.id != req.id),
                        count=count,
                        order_by=cls.user_id,
                        eagerload=['user'])

    @classmethod
    def in_conflict_ou(cls, session, req, count=None):
        """Get all requests conflicting on given request dates.

        and with common user ou (organisational unit)
        """
        return cls.find(session,
                        join=(cls.user),
                        where=(or_(and_(cls.date_from >= req.date_from,
                                        cls.date_to <= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_from),
                               and_(cls.date_from <= req.date_to,
                                    cls.date_to >= req.date_from)),
                               cls.status != 'CANCELED',
                               cls.status != 'DENIED',
                               User.ou == req.user.ou,
                               cls.id != req.id),
                        count=count,
                        order_by=cls.user_id,
                        eagerload=['user'])

    @classmethod
    def in_conflict(cls, session, req, count=None):
        """Get all requests conflicting on dates with given request."""
        return cls.find(session,
                        join=(cls.user),
                        where=(or_(and_(cls.date_from >= req.date_from,
                                        cls.date_to <= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_from),
                               and_(cls.date_from <= req.date_to,
                                    cls.date_to >= req.date_from)),
                               cls.status != 'CANCELED',
                               cls.status != 'DENIED',
                               cls.id != req.id),
                        count=count,
                        order_by=cls.user_id,
                        eagerload=['user'])

    @classmethod
    def get_by_month(cls, session, country, month, year):
        """
        Get all requests for a given month.

        Exclude Recovery requests from result.
        """
        from calendar import monthrange

        date = datetime.now()
        # retrieve first day of the previous month
        # first_month_day = date.replace(day=1) - relativedelta(months=1)
        first_month_day = date.replace(day=1, month=month, year=year)
        # set date at 00:00:00
        first_month_date = first_month_day.replace(hour=0, minute=0, second=0,
                                                   microsecond=0)

        # retrieve last day of the previous month
        last_month_day = monthrange(first_month_day.year,
                                    first_month_day.month)[1]
        # set time at 23:59:59 for this date
        last_month_date = (first_month_day.replace(day=last_month_day, hour=23,
                                                   minute=59, second=59,
                                                   microsecond=0))

        country_id = Countries.by_name(session, country).id

        return cls.find(session,
                        join=(cls.user),
                        where=(or_(and_(cls.date_from >= first_month_date,
                                        cls.date_to <= last_month_date),
                               and_(cls.date_from <= first_month_date,
                                    cls.date_to >= first_month_date),
                               and_(cls.date_from <= last_month_date,
                                    cls.date_to >= last_month_date)),
                               User.country_id == country_id,
                               cls.status == 'APPROVED_ADMIN',
                               cls.vacation_type_id != 4,),
                        order_by=cls.user_id)

    @classmethod
    def get_previsions(cls, session, end_date=None):
        """Retrieve future validated requests per user."""
        # Searching for requests with an timeframe
        #         [NOW()] ---------- ([end_date])?
        # exemples:
        #      <f --r1---- t>
        #                 <f --r2-- t>
        #                       <f ------r3-------- t>
        #      <f ----------- r4 -------------------- t>
        # => Matching period are periods ending after NOW()
        #   and if an end_date is specified periods starting before it:

        if end_date:
            future_requests = session.query(
                cls.user_id, func.sum(cls.days)).\
                filter(cls.date_to >= func.current_timestamp(),
                       cls.date_from < end_date,
                       cls.vacation_type_id == 1,
                       cls.status == 'APPROVED_ADMIN').\
                group_by(cls.user_id).\
                order_by(cls.user_id)
        else:
            future_requests = session.query(
                cls.user_id, func.sum(cls.days)).\
                filter(cls.date_to >= func.current_timestamp(),
                       cls.vacation_type_id == 1,
                       cls.status == 'APPROVED_ADMIN').\
                group_by(cls.user_id).\
                order_by(cls.user_id)

        ret = {}
        for user_id, total in future_requests:
            ret[user_id] = total

        return ret

    @classmethod
    def get_active(cls, session, date=None):
        """
        Get all active requests for give date.

        default to today's date
        """
        from datetime import datetime
        date = date or datetime.now().date()
        try:
            return cls.find(session,
                            join=(cls.user),
                            where=(cls.date_from <= date,
                                   cls.date_to >= date,
                                   cls.status == 'APPROVED_ADMIN',),
                            order_by=cls.user_id)
        except:
            return []

    @property
    def type(self):
        """Get name of chosen vacation type."""
        return _(self.vacation_type.name, self.user.country)

    @property
    def pool(self):
        """Retrieve pool status stored in json."""
        if self.pool_status:
            return json.loads(self.pool_status)
        return {}

    @property
    def summary(self):
        """Get a short string representation of a request, for tooltip."""
        return ('%s: %s - %s' %
                (self.user.name,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y')))

    @property
    def summarycal(self):
        """Get a short string representation of a request.

        for calendar summary.
        """
        label = ' %s' % self.label if self.label else ''
        return ('%s - %.1f %s%s' %
                (self.user.name, self.days, self.type, label))

    @property
    def summarycsv(self):
        """Get a string representation in csv format of a request."""
        # name, datefrom, dateto, number of days, type of days, label, message
        label = '%s' % self.label if self.label else ''
        message = '%s' % self.message if self.message else ''
        return ('%s,%s,%s,%s,%.1f,%s,%s,%s' %
                (self.user.lastname,
                 self.user.firstname,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y'),
                 self.days,
                 self.type,
                 label,
                 message))

    @property
    def summarymail(self):
        """Get a short string representation of a request.

        for mail summary.
        """
        label = ' %s' % self.label if self.label else ''
        return ('%s: %s - %s (%.1f %s%s)' %
                (self.user.name,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y'),
                 self.days,
                 self.type,
                 label))

    @property
    def timestamps(self):
        """
        Return request dates as list of timestamps.

        timestamp are in javascript format
        """
        return [utcify(date)
                for date in daterange(self.date_from, self.date_to)
                if date.isoweekday() not in [6, 7]]

    def add_to_cal(self, caldav_url):
        """Add entry in calendar for request."""
        if self.ics_url:
            log.info('Tried to add to cal request %d but ics_url already set'
                     % self.id)
            return

        if not caldav_url:
            log.info('Tried to add to cal request %d but no url provided'
                     % self.id)
            return

        try:
            # add new entry in caldav
            ics_url = addToCal(caldav_url,
                               self.date_from,
                               self.date_to,
                               self.summarycal)
            # save ics url in request
            self.ics_url = ics_url
            log.info('Request %d added to cal: %s ' % (self.id, ics_url))
        except Exception as err:
            log.exception('Error while adding to calendar')
            self.flag_error(str(err))

    def generate_vcal_entry(self):
        """Generate vcal entry for request."""
        vcal_entry = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:Pyvac Calendar
BEGIN:VEVENT
SUMMARY:%s
DESCRIPTION:%s
DTSTART;VALUE=DATE:%s
DTEND;VALUE=DATE:%s
ORGANIZER;CN=%s:MAILTO:%s
LOCATION:%s
SEQUENCE:0
END:VEVENT
END:VCALENDAR
"""
        vcal_entry = vcal_entry % (
            self.summarycal,
            self.summarycal,
            self.date_from.strftime('%Y%m%d'),
            (self.date_to + relativedelta(days=1)).strftime('%Y%m%d'),
            self.user.firm,
            self.sender_mail,
            self.user.firm)

        return vcal_entry

    def __eq__(self, other):
        """Magic method to allow request comparison."""
        return (
            isinstance(other, self.__class__) and
            hasattr(self, 'id') and
            hasattr(other, 'id') and
            self.id == other.id)

    def __ne__(self, other):
        """Magic method to allow request comparison."""
        return (
            isinstance(other, self.__class__) and
            hasattr(self, 'id') and
            hasattr(other, 'id') and
            self.id != other.id)


class PasswordRecovery(Base):
    """Describe password recovery attempts."""

    hash = Column(Unicode(255), nullable=False, unique=True)
    date_end = Column(DateTime, nullable=False)
    user_id = Column('user_id', ForeignKey(User.id), nullable=False)
    user = relationship(User, backref='recovery')

    @classmethod
    def by_hash(cls, session, hash):
        """Get a recovery entry from a given hash."""
        return cls.first(session, where=(cls.hash == hash,))

    @property
    def expired(self):
        """Check if a recovery entry have expired."""
        from datetime import datetime
        return self.date_end < datetime.now()


class Sudoer(Base):
    """To allow a user to have access to another user interface."""

    source_id = Column(Integer, nullable=False)
    target_id = Column(Integer, nullable=False)

    @classmethod
    def alias(cls, session, user):
        """Retrieve list of aliases for given user."""
        targets = cls.find(session, where=(cls.source_id == user.id,))
        if targets:
            return [User.by_id(session, target.target_id)
                    for target in targets]
        return []

    @classmethod
    def list(cls, session):
        """Retrieve all sudoers entries."""
        return cls.find(session, order_by=cls.source_id)


class Reminder(Base):
    """Describe reminder to send per user/settings.

    Entry is created when the notification reminder has been sent"""

    # type of reminder
    type = Column(Enum('trial_threshold',
                  name='enum_reminder_type'),
                  nullable=False)

    # parameters of reminder
    parameters = Column(UnicodeText(), nullable=False)

    @classmethod
    def by_type(cls, session, type):
        """Get a reminder entry for a given type."""
        return cls.find(session, where=(cls.type == type,))

    @classmethod
    def by_type_param(cls, session, type, parameters):
        """Get recovery entry for a given type and parameters."""
        return cls.first(session, where=(cls.type == type,
                                         cls.parameters == parameters))

    def __repr__(self):
        return "<Reminder #%d: %s (%s)>" % (self.id, self.type,
                                            self.parameters)


def includeme(config):
    """
    Pyramid includeme file for the :class:`pyramid.config.Configurator`
    """

    settings = config.registry.settings

    if 'pyvac.vacation.cp_class.enable' in settings:
        cp_class = asbool(settings['pyvac.vacation.cp_class.enable'])
        if cp_class:
            if 'pyvac.vacation.cp_class.base_file' in settings:
                file = settings['pyvac.vacation.cp_class.base_file']
                CPVacation.initialize(file)

    if 'pyvac.vacation.cp_lu_class.enable' in settings:
        cp_lu_class = asbool(settings['pyvac.vacation.cp_lu_class.enable'])
        if cp_lu_class:
            if 'pyvac.vacation.cp_lu_class.base_file' in settings:
                file = settings['pyvac.vacation.cp_lu_class.base_file']
                CPLUVacation.initialize(file)

    if 'pyvac.vacation.rtt_class.enable' in settings:
        rtt_class = asbool(settings['pyvac.vacation.rtt_class.enable'])
        if rtt_class:
            if 'pyvac.vacation.rtt_class.except_months' in settings:
                except_months = settings['pyvac.vacation.rtt_class.except_months'] # noqa
                RTTVacation.initialize(aslist(except_months))

    if 'pyvac.firm' in settings:
        User.firm = settings['pyvac.firm']

    if 'pyvac.features.users_flagfile' in settings:
        file = settings['pyvac.features.users_flagfile']
        User.load_feature_flags(file)

    if 'pyvac.password.sender.mail' in settings:
        Request.sender_mail = settings['pyvac.password.sender.mail']
