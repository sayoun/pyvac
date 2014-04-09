# -*- coding: utf-8 -*-

import re
import logging
import cryptacular.bcrypt

from sqlalchemy import (Table, Column, ForeignKey, Index, Enum,
                        Integer, Float, Boolean, Unicode, DateTime,
                        UnicodeText)
from sqlalchemy import or_, and_
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.ext.declarative import declared_attr

from .helpers.sqla import (Database, SessionFactory, ModelError,
                           create_engine as create_engine_base,
                           dispose_engine as dispose_engine_base
                           )

from pyvac.helpers.ldap import LdapCache

log = logging.getLogger(__file__)
crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

DBSession = lambda: SessionFactory.get('pyvac')()
Base = Database.register('pyvac')

re_email = re.compile(r'^[^@]+@[a-z0-9]+[-.a-z0-9]+\.[a-z]+$', re.I)


def create_engine(settings, prefix='sqlalchemy.', scoped=False):
    return create_engine_base('pyvac', settings, prefix, scoped)


def dispose_engine():
    dispose_engine_base


class Permission(Base):
    """Describe a user permission"""
    name = Column(Unicode(255), nullable=False, unique=True)


group__permission = Table('group__permission', Base.metadata,
                          Column('group_id', Integer, ForeignKey('group.id')),
                          Column('permission_id',
                                 Integer, ForeignKey('permission.id'))
                          )


class Group(Base):
    """
    Describe user's groups.
    """
    name = Column(Unicode(255), nullable=False, unique=True)
    permissions = relationship(Permission, secondary=group__permission,
                               lazy='select')

    @classmethod
    def by_name(cls, session, name):
        """
        Get a group from a given name.
        """
        return cls.first(session, where=(cls.name == name,))


user__group = Table('user__group', Base.metadata,
                    Column('group_id', Integer, ForeignKey('group.id')),
                    Column('user_id', Integer, ForeignKey('user.id'))
                    )


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

    role = Column(Enum('user', 'manager', 'admin'), nullable=False,
                  name='enum_user_role',
                  default='user')

    manager_id = Column(Integer, ForeignKey(u'user.id'))
    manager = relationship(u'User', remote_side=u'User.id', backref=u'users')
    manager_dn = Column(Unicode(255), nullable=False, default=u'')

    ldap_user = Column(Boolean, nullable=False, default=False)
    dn = Column(Unicode(255), nullable=False, default=u'')

    country = Column(Enum('fr', 'us', 'lu', 'cn'), nullable=False,
                     name='enum_user_country',
                     default='fr')

    @property
    def name(self):
        return u'%s %s' % (self.firstname, self.lastname)\
            if self.firstname and self.lastname else self.login

    def _get_password(self):
        return self._password

    def _set_password(self, password):
        self._password = unicode(crypt.encode(password))

    password = property(_get_password, _set_password)
    password = synonym('_password', descriptor=password)

    @property
    def is_super(self):
        """ Check if user has rights to manage other users """
        return self.role in ('admin', 'manager')

    @property
    def is_admin(self):
        """ Check if user has admin rights """
        return self.role in ('admin',)

    @property
    def manager_mail(self):
        """ Get manager email for a user """
        if not self.ldap_user:
            return self.manager.email
        else:
            ldap = LdapCache()
            user_data = ldap.search_user_by_dn(self.manager_dn)
            return user_data['email']

    @classmethod
    def by_login(cls, session, login):
        """
        Get a user from a given login.
        """
        user = cls.first(session,
                         where=((cls.login == login),)
                         )
        # XXX it's appear that this is not case sensitive !
        return user if user and user.login == login else None

    @classmethod
    def by_email(cls, session, email):
        """
        Get a user from a given email.
        """
        user = cls.first(session,
                         where=((cls.email == email),)
                         )
        # XXX it's appear that this is not case sensitive !
        return user if user and user.email == email else None

    @classmethod
    def by_credentials(cls, session, login, password, ldap=False):
        """
        Get a user from given credentials
        """
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

    def validate(self, session):
        """
        Validate that the current user can be saved.
        """
        errors = []
        if not self.login:
            errors.append(u'login is required')
        else:
            other = User.by_login(session, self.login)
            if other and other.id != self.id:
                errors.append(u'duplicate login %s' % self.login)
        # no need for password for ldap users
        if not self.ldap_user and not self.password:
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
        """
        Get a user from a given role.
        """
        return cls.find(session, where=((cls.role == role),))

    @classmethod
    def get_admin_by_country(cls, session, country):
        """
        Get user with role admin for a specific country
        """
        return cls.first(session,
                         where=(cls.country == country,
                                cls.role == 'admin'),
                         order_by=cls.id)

    @classmethod
    def by_dn(cls, session, user_dn):
        """
        Get a user using ldap user dn
        """
        user = cls.first(session,
                         where=((cls.dn == user_dn),)
                         )
        # XXX it's appear that this is not case sensitive !
        return user if user and user.dn == user_dn else None

    @classmethod
    def by_ldap_credentials(cls, session, login, password):
        """
        Get a user using ldap credentials
        """
        ldap = LdapCache()
        user_data = ldap.authenticate(login, password)
        if user_data is not None:
            login = user_data['login']
            user = User.by_login(session, login)
            # create user if needed
            if not user:
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
                user = User.create_from_ldap(session, user_data, group)
            else:
                # update user with ldap informations in case it changed
                user.email = unicode(user_data['email'])
                user.firstname = unicode(user_data['firstname'])
                user.lastname = unicode(user_data['lastname'])
                user.manager_dn = unicode(user_data['manager_dn'])
                user.dn = unicode(user_data['dn'])

            return user

    @classmethod
    def create_from_ldap(cls, session, data, group):
        """
        Create a new user in database using ldap data information
        """
        user = User(login=unicode(data['login']),
                    email=unicode(data['email']),
                    firstname=unicode(data['firstname']),
                    lastname=unicode(data['lastname']),
                    country=unicode(data['country']),
                    manager_dn=unicode(data['manager_dn']),
                    ldap_user=True,
                    dn=unicode(data['dn']),
                    role=group,
                    )
        # in user group
        user.groups.append(Group.by_name(session, group))
        session.add(user)
        session.flush()

        return user

    def get_admin(self, session):
        """
        Get admin for country of user
        """
        if not self.ldap_user:
            return self.get_admin_by_country(session, self.country)
        else:
            # retrieve from ldap
            ldap = LdapCache()
            return ldap.get_hr_by_country(self.country)


class Request(Base):
    """
    Describe a user request for vacation.
    """

    date_from = Column(DateTime, nullable=False)
    date_to = Column(DateTime, nullable=False)
    days = Column(Float(precision=1), nullable=False)
    choose_type = set(['CP', 'RTT', 'Day off'])

    type = Column(Enum(*choose_type, name='enum_request_type'),
                  nullable=False, default='CP')

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
    # actor who performed last action on request
    actor_id = Column(Integer, nullable=True)

    notified = Column(Boolean, default=False)
    user_id = Column('user_id', ForeignKey(User.id))
    user = relationship(User, backref='requests')

    def update_status(self, status):
        """ Reset notified flag when changing status """
        self.status = status
        self.notified = False

    @classmethod
    def by_manager(cls, session, manager, count=None):
        """
        Get requests for users under given manager.
        """
        return cls.find(session,
                        join=(cls.user),
                        where=(User.manager_id == manager.id,
                               cls.status != 'CANCELED'),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def by_user(cls, session, user, count=None):
        """
        Get requests for given user.
        """
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status != 'CANCELED'),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def by_status(cls, session, status, count=None, notified=False):
        """
        Get requests for given status.
        """
        return cls.find(session,
                        where=(cls.status == status,
                               cls.notified == notified),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def all_for_admin(cls, session, count=None):
        """
        Get all requests manageable by admin.
        """
        return cls.find(session,
                        where=((cls.status != 'CANCELED'),),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def in_conflict(cls, session, req, count=None):
        """
        Get all requests conflicting on dates with given request.
        """
        return cls.find(session,
                        where=(or_(and_(cls.date_from >= req.date_from,
                                        cls.date_to <= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_to),
                               and_(cls.date_from <= req.date_from,
                                    cls.date_to >= req.date_from),
                               and_(cls.date_from <= req.date_to,
                                    cls.date_to >= req.date_from)),
                               cls.status != 'CANCELED',
                               cls.status != 'CANCELED_NOTIFIED',
                               cls.id != req.id),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def get_by_month(cls, session, month=0):
        """
        Get all requests for a given month.
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        from calendar import monthrange

        date = datetime.now()
        # retrieve first day of the previous month
        # first_month_day = date.replace(day=1) - relativedelta(months=1)
        first_month_day = date.replace(day=1)
        # set date at 00:00:00
        first_month_date = first_month_day.replace(hour=0, minute=0, second=0,
                                                   microsecond=0)

        # retrieve last day of the previous month
        last_month_day = monthrange(first_month_day.year,
                                    first_month_day.month)[1]
        # set time at 23:59:59 for this date
        last_month_date = (first_month_day.replace(day=last_month_day, hour=23,
                                                   minute=59, second=59,
                                                   microsecond=0)
                           + relativedelta(months=1))

        return cls.find(session,
                        where=(and_(cls.date_from >= first_month_date,
                                    cls.date_to <= last_month_date),
                               cls.status != 'CANCELED',),
                        order_by=cls.user_id)

    @property
    def summary(self):
        """
        Get a short string representation of a request, for tooltip.
        """
        return ('%s: %s - %s' %
                (self.user.name,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y')))

    @property
    def summarycal(self):
        """
        Get a short string representation of a request, for calendar summary.
        """
        return ('%s - %d %s' %
                (self.user.name, self.days, self.type))

    @property
    def summarycsv(self):
        """
        Get a string representation in csv format of a request.
        """
        # name, datefrom, dateto, number of days, type of days
        return ('%s,%s,%s,%d,%s' %
                (self.user.name,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y'),
                 self.days,
                 self.type))

    @property
    def summarymail(self):
        """
        Get a short string representation of a request, for mail summary.
        """
        return ('%s: %s - %s (%d %s)' %
                (self.user.name,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y'),
                 self.days,
                 self.type))
