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
                        UnicodeText, Index, UniqueConstraint)
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import relationship, synonym, backref
from sqlalchemy.ext.declarative import declared_attr

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
from pyvac.helpers.holiday import utcify, get_holiday

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


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


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

    registration_number = Column(Integer, nullable=True)

    partial_time = Column(Unicode(5), nullable=True)

    firm = ''
    feature_flags = {}
    users_flagfile = ''

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
            return self.created_at

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
        if current_arrival_date.date() < today.date():
            current_arrival_date += relativedelta(months=12)

        if current_arrival_date.date() == today.date():
            return (True, 0)

        delta = (today - current_arrival_date).days
        return (True if delta == 0 else False, abs(delta))

    @property
    def pool(self):
        """Return current pool status amounts for user"""
        return dict([(up.fullname, up) for up in self.pools])

    def set_pool_amount(self, session, poolname, amount, created_at=None):
        """Set pool amount for user, create userpool if it does not exists"""
        pool = Pool.by_name_country(session, poolname, self._country)
        up = UserPool.by_user_pool(session, self, pool)
        if not up:
            entry = UserPool(amount=0, user=self, pool=pool)
            session.flush()
            entry.increment(session, amount, 'heartbeat', created_at=created_at) # noqa
        else:
            raise Exception('This should not happen')
            up.amount = amount

    def get_cycle_anniversary(self, cycle_start, cycle_end):
        """Return user anniversary date if in current cycle boundaries."""
        arrival_date = self.arrival_date
        if not arrival_date:
            return

        current_arrival_date = arrival_date.replace(year=cycle_end.year)
        # if it's already past for this year
        if current_arrival_date > cycle_end:
            current_arrival_date -= relativedelta(months=12)

        if current_arrival_date < cycle_start:
            return

        return current_arrival_date

    def get_seniority(self, today=None):
        """Return how many years the user has been employed."""
        arrival_date = self.arrival_date
        if not arrival_date:
            return 0

        today = today or datetime.now()
        nb_year = today.year - arrival_date.year
        current_arrival_date = arrival_date.replace(year=today.year)
        if today < current_arrival_date:
            nb_year = nb_year - 1

        return nb_year

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
    def get_admin_by_country(cls, session, country, full=False):
        """Get user with role admin for a specific country."""
        method = cls.first
        if full:
            method = cls.find
        return method(session,
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

        # create userpool for this user if needed
        pools = Pool.by_country_active(session, country.id)
        for pool in pools:
            pool_class = pool.vacation_class
            initial_amount = pool_class.get_increment_step(user)
            entry = UserPool(amount=0, user=user, pool=pool)
            session.flush()
            entry.increment(session, initial_amount, 'creation')

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

    def get_admin(self, session, full=False):
        """Get admin for country of user."""
        if not self.ldap_user:
            return self.get_admin_by_country(session, self.country, full=full)
        else:
            # retrieve from ldap
            ldap = LdapCache()
            return ldap.get_hr_by_country(self.country, full=full)

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
    def load_feature_flags(cls):
        """Load features flag per users."""
        try:
            with open(cls.users_flagfile) as fdesc:
                conf = yaml.load(fdesc, YAMLLoader)
            cls.feature_flags = conf.get('users_flags', {})
            log.info('Loaded users feature flags file %s: %s' %
                     (cls.users_flagfile, cls.feature_flags))
        except IOError:
            log.warn('Cannot load users feature flags file %s' %
                     cls.users_flagfile)

    @classmethod
    def save_feature_flags(cls):
        """Save users feature flag data"""
        try:
            with open(cls.users_flagfile, 'w') as out:
                data = {'users_flags': cls.feature_flags}
                yaml.dump(data, out, indent=4,
                          default_flow_style=False)
        except IOError:
            log.warn('Cannot save feature flags file %s' % cls.users_flagfile)

    def has_feature(self, feature):
        """Check if user has a feature enabled."""
        return feature in self.feature_flags.get(self.login, [])

    def add_feature(self, feature, save=False):
        """Add feature for user and save it if needed."""
        user_feature = self.feature_flags.get(self.login, [])
        if feature not in user_feature:
            if self.login not in self.feature_flags:
                # cast in str otherwise yaml will write !!python-unicode and
                # yaml load will fail
                self.feature_flags[str(self.login)] = []
            self.feature_flags[self.login].append(feature)
            if save:
                self.save_feature_flags()

    def del_feature(self, feature, save=False):
        """Delete feature for user and save it if needed."""
        user_feature = self.feature_flags.get(self.login, [])
        if feature in user_feature:
            self.feature_flags[self.login].remove(feature)
            if save:
                self.save_feature_flags()

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
        if self.has_feature('disable_rtt'):
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

        return [{'date': item, 'value': 1, 'flavor': '', 'req_id': None}
                for item in acquired]

    @classmethod
    def get_rtt_taken_history(cls, session, user, year):
        """Get RTT taken history."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        entries = [req for req in user.requests
                   if (req.vacation_type.name == u'RTT') and
                   (req.status in valid_status) and
                   (req.date_from.year == year)]

        return [{'date': req.date_from, 'value': -req.days,
                 'flavor': '', 'req_id': req.id}
                for req in entries]

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
    def get_cp_acquired_history(cls, vac, acquired, user, today=None):
        """Get CP acquired history."""
        today = today or datetime.now()
        cycle_start, _ = vac.get_cycle_boundaries(today)

        cycle_start, _ = vac.get_cycle_boundaries(today)
        if cycle_start < vac.epoch:
            cycle_start = vac.epoch

        if cycle_start.day != 1:
            cycle_start = cycle_start + relativedelta(days=1)

        if user.arrival_date > cycle_start:
            cycle_start = user.arrival_date

        if user.country == 'lu':
            return [{'date': cycle_start, 'value': 200}]

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

        if cycle_start.day != 1:
            cycle_start = cycle_start + relativedelta(days=1)

        if user.arrival_date > cycle_start:
            cycle_start = user.arrival_date

        thresholds = [cycle_start, cycle_end]

        def get_restant(date):
            data = vac.acquired(user, date, session)
            if not data:
                return 0
            extra = data.get('extra', {}).get('allowed', 0)
            return data['restant'] + data.get('n_1', 0) + extra

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
                 'flavor': '',
                 'value': -req.days,
                 'req_id': req.id} for req in entries]

    def get_cp_taken_year(self, session, date):
        """Retrieve taken CP for a user for current year."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        return sum([req.days for req in self.requests
                    if (req.vacation_type.name == u'CP') and
                    (req.status in valid_status) and
                    (req.date_from >= date)])

    def get_cp_taken_cycle(self, session, date_start, date_end,
                           return_req=False):
        """Retrieve taken CP for a user for current cycle."""
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        if return_req:
            return [req for req in self.requests
                    if (req.vacation_type.name == u'CP') and
                    (req.status in valid_status) and
                    (req.date_from >= date_start) and
                    (req.date_to <= date_end)]

        return sum([req.days for req in self.requests
                    if (req.vacation_type.name == u'CP') and
                    (req.status in valid_status) and
                    (req.date_from >= date_start) and
                    (req.date_to <= date_end)])

    @classmethod
    def get_cp_history(cls, session, user, year, today=None):
        """Get CP history for given user: taken + acquired, sorted by date."""
        today = today.replace(year=year) or datetime.now().replace(year=year)
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
        raw_acquired = cls.get_cp_acquired_history(vac, allowed, user, today)
        # add seniority CP bonus if any
        anniv_date = user.get_cycle_anniversary(cycle_start, today)
        cp_bonus = int(math.floor(user.get_seniority(today) / 5))
        if anniv_date and cp_bonus:
            raw_acquired.append({'date': anniv_date,
                                 'flavor': 'seniority',
                                 'value': cp_bonus})

        if user.country == 'lu':
            # XXX: handle expiration date for restant pool
            restant_expire_date = datetime(today.year, 3, 31)
            allowed_data = user.get_cp_usage(session,
                                             today=restant_expire_date,
                                             start=cycle_start, end=today)
            allowed_restant = allowed_data['restant']
            if today >= allowed_restant['expire']:
                raw_acquired.append({'date': allowed_restant['expire'],
                                     'flavor': 'expiration',
                                     'value': -allowed_restant['left']})

        # XXX: handle expiration date for extra pool
        extra = allowed.get('extra')
        if extra and extra.get('absolute'):
            if extra['absolute'] < 0:
                # don't substract 2 times, it's already accounted in restants
                extra['absolute'] = 0
            raw_acquired.append({'date': extra['expire_date'],
                                 'flavor': 'expiration',
                                 'value': -abs(extra['absolute'])})

        acquired = []
        total = 0
        for item in raw_acquired:
            if 'flavor' not in item:
                item['flavor'] = ''
            if 'req_id' not in item:
                item['req_id'] = None
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

    def get_cp_usage(self, session, today=None, start=None, end=None,
                     taken_end=None):
        """Get CP usage for a user."""
        kwargs = {'session': session,
                  'name': u'CP',
                  'country': self.country,
                  'user': self,
                  'today': today,
                  'start': start,
                  'end': end}
        vac = VacationType.by_name_country(**kwargs)
        if not vac:
            return
        allowed = vac.acquired(**kwargs)
        if not allowed:
            return

        cycle_start = allowed['cycle_start']
        cycle_end = allowed['cycle_end']
        if taken_end:
            cycle_end = taken_end
        req_taken = self.get_cp_taken_cycle(session, cycle_start, cycle_end,
                                            return_req=True)
        taken = sum([req.days for req in req_taken])
        log.debug('taken %d for %s -> %s' % (taken, cycle_start, cycle_end))

        return vac.get_left(taken, allowed, req_taken)

    def get_cp_class(self, session):
        kwargs = {'session': session,
                  'name': u'CP',
                  'country': self.country,
                  'user': self}
        vac = VacationType.by_name_country(**kwargs)
        return vac

    def get_lu_holiday(self, today=None):
        """Return list of datetimes in last 3 months for LU user."""
        # retrieve Compensatoire taken history
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        taken = [datetime.strptime(req.message, '%d/%m/%Y')
                 for req in self.requests
                 if (req.vacation_type.name == u'Compensatoire') and
                 (req.status in valid_status)]

        now = today or datetime.now()
        compensatory = [dt for dt in get_holiday(self, year=now.year-1, use_datetime=True) # noqa
                        if (dt not in taken) and
                        (dt.isoweekday() in [6, 7]) and
                        (dt - relativedelta(months=3) <= now <= (dt + relativedelta(months=3)))]  # noqa
        return compensatory


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
    def get_left(cls, taken, allowed, req_taken):
        """Return how much vacation is left after taken has been accounted."""
        raise NotImplementedError

    @classmethod
    def validate_request(cls, user, pool, days, date_from, date_to):
        """Validate request for user for this vacation type."""
        raise NotImplementedError

    @classmethod
    def convert_days(cls, days):
        return days

    @classmethod
    def get_increment_step(cls, **kwargs):
        return 0

    @classmethod
    def check_seniority(cls, userpool):
        """Called every day to check for user seniority bonus."""
        return 0


class CompensatoireVacation(BaseVacation):
    """Implement Compensatoire vacation behavior."""

    name = u'Compensatoire'
    country = u'lu'

    @classmethod
    def acquired(cls, **kwargs):
        """Return acquired vacation this year to current day."""
        raise NotImplementedError

    @classmethod
    def get_left(cls, taken, allowed, req_taken):
        """Return how much vacation is left after taken has been accounted."""
        raise NotImplementedError

    @classmethod
    def validate_request(cls, user, pool, days, holiday_date, request_date):
        """Validate request for user for this vacation type."""
        # check that we request vacations in the allowed period
        if days != 1:
            return ('You can only use 1 Compensatory holiday at a time, '
                    'for a full day.')

        # check that the holiday date is a valid one
        compensatory = user.get_lu_holiday()
        if holiday_date not in compensatory:
            msg = ('%s is not a valid value for Compensatory vacation' %
                   holiday_date.strftime('%d/%m/%Y'))
            return msg

        # check for holiday date < requested date
        if request_date < holiday_date:
            msg = ('You must request a date after %s' %
                   holiday_date.strftime('%d/%m/%Y'))
            return msg

        # check for requested date within holiday date + 3 months
        if request_date > (holiday_date + relativedelta(months=3)):
            msg = ('You must request a date in the following 3 months after %s'
                   % holiday_date.strftime('%d/%m/%Y'))
            return msg


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
    def get_increment_step(cls, user=None, date=None, **kwargs):
        """Get the amount to use to increment a User Pool each cycle."""

        # check if user is using partial time
        # in which case increment should be a fraction of 1 RTT
        if user and user.partial_time:
            # this would return 0.4 for a partial time of '2/5'
            return eval('%s.' % user.partial_time)

        today = date or datetime.now()
        if today.month not in cls.except_months:
            return 1
        return 0

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
    extra_cp = False
    cycle_end_year = None
    cycle_start = None
    delta_restant = 0

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
    def get_increment_step(cls, **kwargs):
        """Get the amount to use to increment a User Pool each cycle."""
        return cls.coeff

    @classmethod
    def get_left(cls, taken, allowed, req_taken):
        """Return how much vacation is left after taken has been accounted."""
        left_data = {}
        cycle_end = allowed['cycle_end']
        restant = allowed['restant']
        n_1 = allowed['n_1']
        acquis = allowed['acquis']
        extra = allowed.get('extra', {})

        left_n_1, left_restant, left_acquis, left_extra = cls.consume(
            taken, n_1, restant, acquis, extra.get('allowed', 0))

        # must handle 3 pools: acquis, restant, and N-1
        ret_n_1 = {
            'allowed': allowed['n_1'],
            'left': left_n_1,
            'expire': cycle_end - relativedelta(months=5)}
        ret_acquis = {
            'allowed': allowed['acquis'],
            'left': left_acquis,
            'expire': cycle_end.replace(year=cycle_end.year + 1)}

        delta_restant = 0
        if cls.extra_cp and cycle_end.year == cls.cycle_end_year:
            # XXX: dirty hack to extend 2017 cycle end until end of year
            delta_restant = cls.delta_restant

        ret_restant = {
            'allowed': allowed['restant'],
            'left': left_restant,
            'expire': allowed['cycle_end'] + relativedelta(months=delta_restant)}  # noqa
        left_data['acquis'] = ret_acquis
        left_data['restant'] = ret_restant
        left_data['n_1'] = ret_n_1
        left_data['taken'] = taken

        # trouver les restants a garder -> extra structure
        if extra:
            # handle extra structure
            expire_date = extra['expire_date']
            left_data['extra'] = {
                'left': left_extra,
                'allowed': extra['allowed'],
                'type': extra['type'],
                'expire': expire_date,
            }

        return left_data

    @classmethod
    def consume(cls, taken, n_1, restant, acquis, extra=None):
        """Remove taken CP from N-1 pool then Restant pool then Acquis pool."""

        # TODO: order pools by expiration date and consume in order
        # this way it's generic ?

        exceed = 0
        if n_1 < 0:
            restant = restant + n_1
            left_n_1 = 0
            n_1 = 0

        left_n_1 = n_1 - abs(taken)
        if left_n_1 < 0:
            exceed = abs(left_n_1)
            left_n_1 = 0

        left_extra = extra - exceed
        if left_extra < 0:
            exceed = abs(left_extra)
            left_extra = 0
        else:
            exceed = 0

        left_restant = restant - exceed
        if left_restant < 0:
            exceed = abs(left_restant)
            left_restant = 0
            left_acquis = acquis - exceed
        else:
            left_acquis = acquis

        return left_n_1, left_restant, left_acquis, left_extra

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
    def check_seniority(cls, userpool):
        """Called every day to check for user seniority bonus."""
        cp_bonus = 0
        # only do this for 'acquis' pool
        if userpool.pool.name == 'restant':
            return 0

        user = userpool.user
        if user.anniversary[0]:
            cp_bonus = int(math.floor(user.seniority / 5))

        return cp_bonus

    @classmethod
    def get_acquis(cls, user, starting_date, today=None):
        """Retrieve amount of acquis for CP."""
        today = today or datetime.now()
        delta = relativedelta(starting_date, today)
        months = abs(delta.months)
        years = abs(delta.years)

        acquis = None
        cp_bonus = 0
        # add bonus CP based on arrival_date, 1 more per year each 5 years
        # cp bonus are added on the last acquisition day of previous cycle,
        # so on 31/05 of year - 1
        anniv_date = user.get_cycle_anniversary(starting_date, today)
        if anniv_date and ((years > 0) or
                           (today > anniv_date > starting_date)):
            cp_bonus = int(math.floor(user.seniority / 5))

        # this if or the pivot date when acquis becomes restants
        if not months and years:
            months = 12
            acquis = 25 + cp_bonus

        log.debug('%s: using coeff %s * months %s + (bonus %s)' %
                  (user.login, cls.coeff, months, cp_bonus))
        acquis = acquis or (months * cls.coeff + cp_bonus)
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
        extra = {}
        try:
            start, end = cls.get_cycle_boundaries(today, raising=True)
            cycle_start = start
            # do not go into a recursive loop if user is in first cycle
            if (kwargs.get('start') == start) and (kwargs.get('end') == end):
                raise FirstCycleException()
            # use user arrival_date if after starting cycle date
            if user.arrival_date > start:
                start = user.arrival_date
            acquis = cls.get_acquis(user, start, today)
            previous_usage = user.get_cp_usage(session, today=start,
                                               start=cycle_start, end=end)
            taken = user.get_cp_taken_cycle(session, start, end)
            restant = previous_usage['acquis']['left']

            # only use extra pool for a specific cycle
            if cls.extra_cp and cycle_start == cls.cycle_start:
                extra_expire = cycle_start + relativedelta(months=cls.delta_restant) # noqa
                extra = {'type': 'restants',
                         'allowed': previous_usage['restant']['left'],
                         'expire_date': extra_expire}
                # extra are only valid until end of civil year in this cycle
                if today > extra_expire:
                    taken = user.get_cp_taken_cycle(session, start,
                                                    extra_expire)
                    extra['absolute'] = extra['allowed'] - taken
                    log.info('extra expired for %s, capping to taken '
                             'value: %d (from %d)'
                             % (user.login, taken, extra['allowed']))
                    if extra['allowed'] > taken:
                        extra['allowed'] = taken

        except FirstCycleException:
            # cannot go back before first cycle, so use current cycle values
            start, end = cls.get_cycle_boundaries(today)
            # use user arrival_date if after starting cycle date
            if user.arrival_date > start:
                start = user.arrival_date
            acquis = cls.get_acquis(user, start, today)
            epoch_restants = cls.users_base.get(user.login,
                                                {'restants': 0, 'n_1': 0})
            restant = epoch_restants['restants']
            n_1 = epoch_restants['n_1']
            n_1_expire = end - relativedelta(months=5)
            # n_1 are only valid until end of civil year in first cycle
            if today > n_1_expire:
                taken = user.get_cp_taken_cycle(session, start, n_1_expire)
                log.info('n_1 expired for %s, capping to taken value: %d'
                         % (user.login, taken))
                if n_1 > taken:
                    n_1 = taken
            start = cls.epoch

        return {'acquis': acquis, 'restant': restant,
                'n_1': n_1,
                'extra': extra,
                'cycle_start': start, 'cycle_end': end}

    @classmethod
    def validate_request(cls, user, pool, days, date_from, date_to):
        """Validate request regarding user pool."""
        pool = user.pool
        if not pool:
            return

        # check that we request vacations in the allowed cycle
        expire_date = pool['CP acquis'].date_end
        if not (date_from <= date_to <= expire_date):
            msg = ('CP can only be used until %s.' %
                   expire_date.strftime('%d/%m/%Y'))
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
    def get_left(cls, taken, allowed, req_taken):
        """Return how much vacation is left after taken has been accounted."""
        cycle_end = allowed['cycle_end']
        restant = allowed['restant']
        acquis = allowed['acquis']

        # compute taken values regarding epoch for converting if necessary
        tot_taken = 0
        for req in req_taken:
            # this is the date when the feature has been released
            if req.created_at < datetime(2016, 7, 26):
                tot_taken += cls.convert_days(req.days)
            else:
                tot_taken += req.days
        taken = tot_taken

        left_restant, left_acquis = cls.consume(taken, restant, acquis)

        delta_restant = 3
        if cycle_end.year == 2017:
            # XXX: dirty hack to extend first cycle end for one more year
            delta_restant = 12
        delta_acquis = 0
        if cycle_end.year == 2016:
            # XXX: dirty hack to extend first cycle end for one more year
            delta_acquis = 12

        # must handle 2 pools: acquis, restant
        ret_acquis = {
            'allowed': allowed['acquis'],
            'left': left_acquis,
            # add 3 months here
            'expire': cycle_end + relativedelta(months=3) + relativedelta(months=delta_acquis)} # noqa
        ret_restant = {
            'allowed': allowed['restant'],
            'left': left_restant,
            # add 3 months here
            'expire': allowed['cycle_end'].replace(year=cycle_end.year - 1) + relativedelta(months=delta_restant)} # noqa
        return {'acquis': ret_acquis, 'restant': ret_restant,
                'taken': taken}

    @classmethod
    def consume(cls, taken, restant, acquis, **kwargs):
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
        """Retrieve amount of acquis for CP LU."""
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
            acquis = 200 + cp_bonus

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
            previous_usage = user.get_cp_usage(session, today=dt)
            if not previous_usage:
                left_acquis = 0
            else:
                left_acquis = previous_usage['acquis']['left']
                # previous acquis are only valid 3 months
                if today > previous_usage['acquis']['expire']:
                    left_acquis = 0
            restant = left_acquis
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
        # check that the user has at least 3 months of seniority
        if user.arrival_date:
            today = datetime.now()
            delta = today - user.arrival_date
            if delta.days < (3 * 31):
                msg = 'You need 3 months of seniority before using your CP'
                return msg

        pool = user.pool
        if not pool:
            return

        total_left = pool['CP acquis'].amount + pool['CP restant'].amount

        if total_left <= 0:
            msg = 'No CP left to take.'
            return msg

        # check that we have enough CP to take
        if days > total_left:
            msg = 'You only have %d CP to use.' % total_left
            return msg

        # check that we request vacations in the allowed cycle
        expire_date = pool['CP acquis'].date_end
        if not (date_from <= date_to <= expire_date):
            msg = ('CP can only be used until %s.' %
                   expire_date.strftime('%d/%m/%Y'))
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

    def get_class(self, country):
        vacation_name = '%s_%s' % (self.name, country)
        return self._vacation_classes.get(vacation_name)


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

    def flag_error(self, message, session):
        """ Set request in ERROR and assign message """
        RequestHistory.new(session, self, self.status, 'ERROR')
        self.status = 'ERROR'
        self.error_message = message

    def get_admin(self, session):
        if self.status == 'APPROVED_ADMIN' and self.last_action_user_id:
            last_user = User.by_id(session, self.last_action_user_id)
            if last_user and last_user.is_admin:
                return last_user
        return

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
    def by_user_future_approved(cls, session, user, count=None,
                                date_from=None):
        """Get pending requests for given user in the future.

        retrieve status = APPROVED_ADMIN
        """
        date_from = date_from or datetime.now().replace(day=1)
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status == 'APPROVED_ADMIN',
                               cls.date_from >= date_from,
                               ),
                        count=count,
                        order_by=(cls.user_id, cls.date_from.desc()))

    @classmethod
    def by_user_future_breakdown(cls, session, user, count=None):
        """Get requests for given user in the future.

        Only retrieve requests for half-days."""
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status != 'CANCELED',
                               cls.status != 'DENIED',
                               cls.status != 'ERROR',
                               cls.date_from >= datetime.now(),
                               cls.days < 1),
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
    def get_by_month(cls, session, country, month, year, sage_order=False,
                     first_month_date=None, last_month_date=None):
        """
        Get all requests for a given month.

        Exclude Recovery requests from result.
        """
        from calendar import monthrange

        date = datetime.now()
        # retrieve first day of the previous month
        # first_month_day = date.replace(day=1) - relativedelta(months=1)
        if not first_month_date:
            first_month_day = date.replace(day=1, month=month, year=year)
            # set date at 00:00:00
            first_month_date = first_month_day.replace(hour=0, minute=0,
                                                       second=0,
                                                       microsecond=0)

        # retrieve last day of the previous month
        if not last_month_date:
            last_month_day = monthrange(first_month_day.year,
                                        first_month_day.month)[1]
            # set time at 23:59:59 for this date
            last_month_date = (first_month_day.replace(day=last_month_day,
                                                       hour=23,
                                                       minute=59, second=59,
                                                       microsecond=0))

        country_id = Countries.by_name(session, country).id

        order_by = cls.user_id
        if sage_order:
            order_by = (User.registration_number, cls.date_from,
                        cls.vacation_type_id)

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
                        order_by=order_by)

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
    def pool_left(self):
        """Retrieve pool left status."""
        if self.pool:
            pool = self.pool
            if self.type == 'CP':
                if 'acquis' in pool:
                    return pool.get('n_1', {}).get('left', 0) + pool['restant']['left'] + pool['acquis']['left'] # noqa
                else:
                    # new pool format
                    # {u'CP acquis': 12.48, u'CP restant': 25.0, u'RTT': 12.0}
                    return pool.get('CP acquis', 0) + pool.get('CP restant', 0)
            else:
                # RTT
                if 'left' in pool:
                    return pool['left']
                else:
                    # new pool format
                    return pool.get('RTT', 0)
        return {}

    def refund_userpool(self, session):
        """refund userpool amount in case of CANCEL/DENIED."""
        UserPool.increment_request(session, self)

    @property
    def sudoed(self):
        """Retrieve is request was sudoed."""
        if self.status == 'APPROVED_ADMIN':
            if len(self.history) == 1:
                for entry in self.history:
                    if entry.sudo_user_id:
                        return entry.sudo_user

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
        days = self.days
        # XXX: must convert CPLU vacation to hours until 2017 cycle
        if self.user.country == 'lu':
            if self.type == 'CP':
                if self.created_at < datetime(2016, 7, 26):
                    days = CPLUVacation.convert_days(days)
            if self.type == 'Maladie':
                days = CPLUVacation.convert_days(days)
            if self.type == 'Compensatoire':
                days = CPLUVacation.convert_days(days)

        return ('%s,%s,%s,%s,%s,%.1f,%s,%s,%s' %
                (self.user.registration_number or '',
                 self.user.lastname,
                 self.user.firstname,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y'),
                 days,
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
    def is_oldcplu(self):
        # XXX: must convert CPLU vacation to hours until 2017 cycle
        if (self.user.country == 'lu' and self.type == 'CP' and
                (self.created_at < datetime(2016, 7, 26))):
            return True

        return False

    @property
    def timestamps(self):
        """
        Return request dates as list of timestamps.

        timestamp are in javascript format
        """
        return [utcify(date)
                for date in daterange(self.date_from, self.date_to)
                if date.isoweekday() not in [6, 7]]

    @property
    def dates(self):
        """Return request dates as list."""
        return [date for date in daterange(self.date_from, self.date_to)
                if date.isoweekday() not in [6, 7]]

    def add_to_cal(self, caldav_url, session):
        """
        Add entry in calendar for request
        """
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
            self.flag_error(str(err), session)

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
    user = relationship(User,
                        backref=backref('recovery', cascade='all,delete'),
                        cascade='all,delete',
                        passive_deletes=True)

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


class RequestHistory(Base):
    """
    Store history of all actions/changes for a given request
    """
    # source request
    req_id = Column('req_id', ForeignKey(Request.id), nullable=False)
    request = relationship(Request, backref='history')
    # status before the change
    old_status = Column(Unicode(255))
    # status after the change
    new_status = Column(Unicode(255))
    # actor who performed action on request
    user_id = Column(Integer, ForeignKey(User.id), nullable=True)
    user = relationship(User, foreign_keys=[user_id],
                        primaryjoin=user_id == User.id)
    # actor if current user has been sudoed
    sudo_user_id = Column(Integer, ForeignKey(User.id), nullable=True)
    sudo_user = relationship(User, foreign_keys=[sudo_user_id],
                             primaryjoin=sudo_user_id == User.id)
    # vacation_type pool counters when the action has been made
    pool_status = Column(UnicodeText())
    # why this request
    message = Column(UnicodeText())
    # reason of cancel or deny
    reason = Column(UnicodeText())
    # in case of ERROR to store the error message
    error_message = Column(UnicodeText())

    @property
    def pool(self):
        """Retrieve pool status stored in json."""
        if self.pool_status:
            return json.loads(self.pool_status)
        return {}

    @property
    def pool_left(self):
        """Retrieve pool left status."""
        if self.pool:
            pool = self.pool
            if self.request.type == 'CP':
                if 'acquis' in pool:
                    return pool.get('n_1', {}).get('left', 0) + pool['restant']['left'] + pool['acquis']['left'] # noqa
                else:
                    # new pool format
                    # {u'CP acquis': 12.48, u'CP restant': 25.0, u'RTT': 12.0}
                    return pool.get('CP acquis', 0) + pool.get('CP restant', 0)
            else:
                # RTT
                if 'left' in pool:
                    return pool['left']
                else:
                    # new pool format
                    return pool.get('RTT', 0)
        return {}

    @classmethod
    def new(cls, session, request, old_status, new_status, user=None,
            pool_status=None, message=None, reason=None, error_message=None,
            sudo_user=None):
        user_id = user.id if user else None
        # check to see how to retrieve sudo status/info
        sudo_user_id = sudo_user.id if sudo_user else None

        entry = cls(request=request,
                    old_status=old_status,
                    new_status=new_status,
                    user_id=user_id,
                    sudo_user_id=sudo_user_id,
                    pool_status=pool_status,
                    message=message,
                    reason=reason,
                    error_message=error_message,
                    )
        session.add(entry)
        session.flush()

        return entry

    @classmethod
    def by_user(cls, session, user_id):
        """Return all entries for given user"""
        return cls.find(session, where=(cls.user_id == user_id,))


class EventLog(Base):
    """Store an event log of all actions/changes happening."""

    # source of action: pool, userpool
    source = Column(Unicode(255), nullable=False)
    # source id if applicable  do not use ForeignKey
    source_id = Column(Integer, nullable=True)
    # type of event: increment, decrement, status, clone, expire
    type = Column(Unicode(255), nullable=False)
    # when we need additionnal information: seniority, heartbeat, request
    comment = Column(Unicode(255), nullable=False)
    # changes applied if needed
    delta = Column(Float(precision=2), nullable=True)
    # extra id if applicable  do not use ForeignKey
    extra_id = Column(Integer, nullable=True)

    @declared_attr
    def __table_args__(cls):  # noqa
        return (Index('idx_%s_source_id' % cls.__tablename__, 'source_id'),
                Index('idx_%s_type' % cls.__tablename__, 'type'),
                Index('idx_%s_comment' % cls.__tablename__, 'comment'),
                Index('idx_%s_extra_id' % cls.__tablename__, 'extra_id'),
                Index('idx_%s_type_comment' % cls.__tablename__,
                      'type', 'comment'),
                Index('idx_%s_source_id_type' % cls.__tablename__,
                      'source_id', 'type'),
                Index('idx_%s_source_id_type_comment' % cls.__tablename__,
                      'source_id', 'type', 'comment'),
                )

    @classmethod
    def add(cls, session, source, type, comment=None, delta=None,
            created_at=None, extra_id=None):
        source_name = source
        if not isinstance(source, basestring):
            source_name = source.__class__.__name__.lower()

        kwargs = {
            'source': source_name,
            'source_id': source.id,
            'type': type,
            'delta': delta,
            'comment': comment,
            'extra_id': extra_id,
        }

        if created_at:
            kwargs['created_at'] = created_at

        entry = cls(**kwargs)
        session.add(entry)
        session.flush()

        return entry

    @classmethod
    def by_source_type(cls, session, source, type, comment):
        return cls.find(session,
                        where=(cls.source_id == source.id,
                               cls.type == type,
                               cls.comment == comment),
                        )

    @classmethod
    def by_type_comment(cls, session, type, comment):
        return cls.find(session,
                        where=(cls.type == type,
                               cls.comment == comment),
                        )

    def __repr__(self):
        try:
            return "<EventLog #%d: %s (#%d) -> %s | %s | %s >" % (
                self.id, self.source, self.source_id, self.type,
                self.comment, self.delta)
        except:
            return object.__repr__(self)


class Pool(Base):
    """Describe a vacation pool entry."""

    name = Column(Unicode(255), nullable=False)
    alias = Column(Unicode(255), nullable=True)
    date_start = Column(DateTime, nullable=False)
    date_end = Column(DateTime, nullable=False)
    # store date of last increment process
    date_last_increment = Column(DateTime, nullable=False, default=func.now())

    status = Column(Enum('active', 'inactive', 'expired',
                         name='enum_pool_status'),
                    nullable=False, default='active')

    vacation_type_id = Column('vacation_type_id', ForeignKey(VacationType.id),
                              nullable=False)
    vacation_type = relationship(VacationType, backref='pools')
    # XXX: handle CP LU this way ?
    country_id = Column('country_id', ForeignKey(Countries.id))
    country = relationship(Countries, backref='pools')

    pool_group = Column(Unicode(255), nullable=True)

    @declared_attr
    def __table_args__(cls):  # noqa
        return (UniqueConstraint('date_start', 'date_end', 'vacation_type_id',
                                 'country_id', 'name',
                                 name='uq_start_end_type_ctry_name'),
                )

    @classmethod
    def by_name(cls, session, name):
        """Get pools for a given name."""
        return cls.find(session, where=(cls.name == name,))

    @classmethod
    def by_pool_group(cls, session, pool_group):
        """Get pools in the same pool_group."""
        return cls.find(session, where=(cls.pool_group == pool_group,
                                        cls.status == 'active'))

    @classmethod
    def by_name_country(cls, session, name, country):
        """Get a pool from a given name and country."""
        return cls.first(session, where=(cls.country == country,
                                         cls.name == name,
                                         cls.status == 'active'))

    @classmethod
    def by_status(cls, session, status):
        """Get a pool from a given status."""
        if not isinstance(status, (list, tuple)):
            status = [status]
        return cls.find(session, where=(cls.status.in_(status),))

    @classmethod
    def by_country_active(cls, session, country_id):
        """Get pools for a given name."""
        return cls.find(session, where=(cls.country_id == country_id,
                                        cls.status == 'active'))

    @classmethod
    def clone(cls, session, pool, shift=None, date_start=None, date_end=None,
              pool_group=None, date_last_increment=None):
        """Clone a pool from an existing one

        with a 12 months shift for date boundaries if nothing is provided."""
        new_date_start = pool.date_start + relativedelta(months=shift or 12)
        new_date_end = pool.date_end + relativedelta(months=shift or 12)
        if date_start:
            new_date_start = date_start
        if date_end:
            new_date_end = date_end
        date_last_increment = date_last_increment or datetime.now()

        entry = cls(name=pool.name,
                    alias=pool.alias,
                    date_start=new_date_start,
                    date_end=new_date_end,
                    status='active',
                    vacation_type=pool.vacation_type,
                    country=pool.country,
                    pool_group=pool_group,
                    date_last_increment=date_last_increment,
                    )
        session.add(entry)
        session.flush()

        EventLog.add(session, pool, 'clone', comment='heartbeat')

        return entry

    @property
    def fullname(self):
        fullname = ''
        if self.vacation_type.name != self.name:
            fullname = '%s ' % self.vacation_type.name
        return '%s%s' % (fullname, self.name)

    @property
    def vacation_class(self):
        vacation_name = self.vacation_type.name

        vacation_name = '%s_%s' % (self.vacation_type.name, self.country.name)
        return VacationType._vacation_classes.get(vacation_name)

    @property
    def in_first_month(self):
        today = datetime.now()
        return self.date_start.month == today.month

    @property
    def in_last_month(self):
        today = datetime.now()
        return self.date_end.month == today.month

    def expire(self, session):
        self.status = 'expired'
        EventLog.add(session, self, 'expire', comment='heartbeat')

    def __repr__(self):
        try:
            return "<Pool #%d: %s (%s) | %s>" % (self.id, self.name,
                                                 self.vacation_type.name,
                                                 self.country.name)
        except:
            return object.__repr__(self)


class UserPool(Base):
    """Describe a user vacation pool entry."""

    amount = Column(Float(precision=2), nullable=False)

    user_id = Column('user_id', ForeignKey(User.id), nullable=False)
    user = relationship(User, backref=backref('pools', cascade='all,delete'),
                        primaryjoin="and_(User.id==UserPool.user_id, UserPool.pool_id==Pool.id, Pool.status=='active')",    # noqa
                        cascade='all,delete',
                        passive_deletes=True)

    pool_id = Column('pool_id', ForeignKey(Pool.id), nullable=False)
    pool = relationship(Pool, backref='user_pools')

    @classmethod
    def by_user_pool(cls, session, user, pool):
        """Get a userpool for a given user and pool."""
        return cls.first(session, where=(cls.user == user,
                                         cls.pool == pool))

    @classmethod
    def by_user(cls, session, user):
        """Get all userpools for a given user."""
        return cls.find(session, where=(cls.user == user,))

    @classmethod
    def by_pool(cls, session, pool):
        """Get all userpools for a given pool."""
        return cls.find(session, where=(cls.pool == pool,))

    @property
    def name(self):
        """Return name of associated pool."""
        return self.pool.name

    @property
    def fullname(self):
        """Return fullname of associated pool."""
        return self.pool.fullname

    @property
    def date_start(self):
        """Return date_start of associated pool."""
        return self.pool.date_start

    @property
    def date_end(self):
        """Return date_end of associated pool."""
        return self.pool.date_end

    def increment(self, session, amount, comment, created_at=None):
        self.amount = self.amount + amount
        EventLog.add(session, self, 'increment', comment=comment, delta=amount,
                     created_at=created_at)

    def increment_month(self, session, need_increment):
        """Called once per month to increment the user pool amount."""
        today = datetime.now()
        pool_class = self.pool.vacation_class
        if need_increment:
            log.info('pool %r to increment for user %s' % (self.pool, self.user.login)) # noqa
            months = diff_month(today, self.pool.date_last_increment)
            log.info('%d months since last update' % months)
            for cpt in range(months):
                date = self.pool.date_last_increment + relativedelta(months=cpt + 1) # noqa
                delta = pool_class.get_increment_step(user=self.user, date=date) # noqa
                self.amount = self.amount + delta

                log.debug('incremented user %s -> %s' % (self.user.login, delta)) # noqa

                EventLog.add(session, self, 'increment', comment='heartbeat',
                             delta=delta)

        # check that we did not have already credited seniority for this user
        evt = EventLog.by_source_type(session, self, 'increment', 'seniority')
        if not evt:
            seniority_bonus = pool_class.check_seniority(self)
            if seniority_bonus:
                self.amount = self.amount + seniority_bonus

                EventLog.add(session, self, 'increment', comment='seniority',
                             delta=seniority_bonus)

    def decrement(self, session, amount, comment, created_at=None):
        self.amount = self.amount - amount
        EventLog.add(session, self, 'decrement', comment=comment, delta=amount,
                     created_at=created_at)

    @classmethod
    def decrement_request(cls, session, request):
        # which userpool do we need to modify
        delta = request.days
        comment = 'Request #%d' % request.id
        userpools = [up for up in request.user.pools
                     if up.pool.vacation_type == request.vacation_type]
        if not userpools:
            return
        created_at = request.date_from
        userpool = userpools[0]
        if userpool.pool.pool_group:
            # in case of a pool_group
            # we need to decrement pools in order of date expiration
            # and report the extra in the other pool
            # example: restant=4 acquis=10, need to decrement 6
            # we'll have restant=0 acquis=8 after this operation
            # 1. order the userpools by expiration date (date_end)
            userpools.sort(key=lambda t: t.date_end)
            # 2. decrement userpool in order of date expiration
            for idx, up in enumerate(userpools, start=1):
                if not delta:
                    continue
                # in case one pool is negative and it's not the last pool
                # probably restant and not acquis
                if up.amount < 0 and idx != len(userpools):
                    continue
                up.amount = up.amount - abs(delta)
                if up.amount < 0:
                    # we consumed more than what was available
                    left = abs(delta) + up.amount
                    delta = abs(up.amount)
                    # if we are at the last pool, keep it as negative
                    # otherwise reset to 0
                    if idx != len(userpools):
                        up.amount = 0
                    else:
                        if round(left + delta) == request.days:
                            left = request.days
                    if left:
                        EventLog.add(session, up, 'decrement', comment=comment,
                                     delta=left, extra_id=request.id,
                                     created_at=created_at)
                else:
                    EventLog.add(session, up, 'decrement', comment=comment,
                                 delta=delta, extra_id=request.id,
                                 created_at=created_at)
                    delta = 0
        else:
            userpool.amount = userpool.amount - delta
            EventLog.add(session, userpool, 'decrement', comment=comment,
                         delta=delta, extra_id=request.id,
                         created_at=created_at)

    @classmethod
    def increment_request(cls, session, request):
        """Used in case of refund"""
        comment = 'Request #%d' % request.id
        events = EventLog.by_type_comment(session, 'decrement', comment)
        # for each events, rollback/refund the userpool
        # this way if a request has consumed multiple pools, it will refund
        # each one for the correct amount
        for event in events:
            up = UserPool.by_id(session, event.source_id)
            up.amount = up.amount + event.delta
            EventLog.add(session, up, 'increment', comment=comment,
                         delta=event.delta, extra_id=request.id,
                         created_at=request.date_from)

    def get_pool_history(self, session, user):
        """Return all events for a userpool."""
        history = []
        events = EventLog.find(session,
                               where=(EventLog.source == "userpool",
                                      EventLog.source_id == self.id),
                               order_by=EventLog.id)
        for evt in events:
            delta = evt.delta
            if evt.type == 'decrement' and delta > 0:
                delta = -delta
            item = {'date': evt.created_at, 'value': delta,
                    'name': self.pool.name, 'flavor': None,
                    'req_id': None}
            if evt.comment != 'heartbeat' and evt.comment:
                item['flavor'] = evt.comment
            if evt.extra_id and 'Request #' in evt.comment:
                item['req_id'] = evt.extra_id
            history.append(item)

        return history

    def __repr__(self):
        try:
            return "<UserPool #%d: %s (%s) | %s>" % (self.id, self.fullname,
                                                     self.amount,
                                                     self.user.login)
        except:
            return object.__repr__(self)


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

    if 'pyvac.vacation.extra_cp.enable' in settings:
        extra_cp = asbool(settings['pyvac.vacation.extra_cp.enable'])
        if extra_cp:
            CPVacation.extra_cp = True
            if 'pyvac.vacation.extra_cp.cycle_end_year' in settings:
                CPVacation.cycle_end_year = int(settings['pyvac.vacation.extra_cp.cycle_end_year']) # noqa
            if 'pyvac.vacation.extra_cp.cycle_start' in settings:
                date = settings['pyvac.vacation.extra_cp.cycle_start']
                CPVacation.cycle_start = datetime.strptime(date, '%d/%m/%Y')
            if 'pyvac.vacation.extra_cp.delta_restant' in settings:
                CPVacation.delta_restant = int(settings['pyvac.vacation.extra_cp.delta_restant']) # noqa

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
        User.users_flagfile = settings['pyvac.features.users_flagfile']
        User.load_feature_flags()

    if 'pyvac.password.sender.mail' in settings:
        Request.sender_mail = settings['pyvac.password.sender.mail']
