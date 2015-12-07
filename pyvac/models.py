# -*- coding: utf-8 -*-

import re
import logging
from datetime import datetime, timedelta
import cryptacular.bcrypt

from sqlalchemy import (Table, Column, ForeignKey, Enum,
                        Integer, Float, Boolean, Unicode, DateTime,
                        UnicodeText, func)
from sqlalchemy import or_, and_
from sqlalchemy.orm import relationship, synonym

from .helpers.sqla import (Database, SessionFactory, ModelError,
                           create_engine as create_engine_base,
                           dispose_engine as dispose_engine_base
                           )

from pyvac.helpers.ldap import LdapCache
from pyvac.helpers.i18n import translate as _
from pyvac.helpers.calendar import addToCal

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


class Countries(Base):
    """
    Describe allowed countries for user
    """
    name = Column(Unicode(255), nullable=False)

    @classmethod
    def by_name(cls, session, name):
        """
        Get a country from a given name.
        """
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

    @property
    def name(self):
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
        """ Check if user has rights to manage other users """
        return self.role in ('admin', 'manager')

    @property
    def is_admin(self):
        """ Check if user has admin rights """
        return self.role in ('admin',)

    @property
    def is_manager(self):
        """ Check if user has admin rights """
        return self.role in ('manager',)

    def is_sudoer(self, session):
        """ Check if user has sudoer rights """
        return Group.by_name(session, 'sudoer') in self.groups

    @property
    def manager_mail(self):
        """ Get manager email for a user """
        if not self.ldap_user:
            return self.manager.email
        else:
            ldap = LdapCache()
            user_data = ldap.search_user_by_dn(self.manager_dn)
            return user_data['email']

    @property
    def manager_name(self):
        """ Get manager name for a user """
        if not self.ldap_user:
            return self.manager.name
        else:
            ldap = LdapCache()
            user_data = ldap.search_user_by_dn(self.manager_dn)
            return user_data['login']

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

    def validate(self, session, ldap=False):
        """
        Validate that the current user can be saved.
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
        """
        Get a user from a given role.
        """
        return cls.find(session, where=((cls.role == role),))

    @classmethod
    def by_country(cls, session, country_id):
        """
        Get users for a given country.
        """
        return cls.find(session, where=((cls.country_id == country_id),))

    @classmethod
    def get_admin_by_country(cls, session, country):
        """
        Get user with role admin for a specific country
        """
        return cls.first(session,
                         join=(cls._country),
                         where=(Countries.name == country,
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
        """
        Create a new user in database using ldap data information
        """
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
        # put in correct group
        user.groups.append(Group.by_name(session, group))
        session.add(user)
        session.flush()

        return user

    @classmethod
    def sync_ldap_info(cls, session):
        """
        Resynchronize ldap information in database, for changes in role/units
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
        """
        Get admin for country of user
        """
        if not self.ldap_user:
            return self.get_admin_by_country(session, self.country)
        else:
            # retrieve from ldap
            ldap = LdapCache()
            return ldap.get_hr_by_country(self.country)

    @property
    def country(self):
        """
        Get name of associated country.
        """
        return self._country.name

    @classmethod
    def for_admin(cls, session, admin):
        """
        Get all users for an admin regarding his country
        """
        return cls.find(session,
                        where=(cls.country_id == admin.country_id,
                               cls.id != admin.id,
                               cls.ldap_user == admin.ldap_user,
                               ),
                        order_by=cls.lastname)

    def get_rtt_taken_year(self, session, year):
        """ Retrieve taken RTT for a user for current year """
        valid_status = ['PENDING', 'ACCEPTED_MANAGER', 'APPROVED_ADMIN']
        return sum([req.days for req in self.requests
                    if (req.vacation_type.name == u'RTT')
                    and (req.status in valid_status)
                    and (req.date_from.year == year)])

    def get_rtt_usage(self, session):
        """ Get RTT usage for a user """
        allowed = VacationType.by_name_country(session, name=u'RTT',
                                               country=self.country,
                                               user=self)
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


vacation_type__country = Table('vacation_type__country', Base.metadata,
                               Column('vacation_type_id', Integer,
                                      ForeignKey('vacation_type.id')),
                               Column('country_id', Integer,
                                      ForeignKey('countries.id'))
                               )


class BaseVacation(object):

    name = None

    @classmethod
    def acquired(cls, **kwargs):
        """ Return acquired vacation this year to current day. """
        raise NotImplementedError


class RTTVacation(BaseVacation):

    name = u'RTT'

    @classmethod
    def acquired(cls, **kwargs):
        """ Return acquired vacation this year to current day.

        We acquire one RTT at the start of each month except in august and
        december.
        """
        start_month = 1
        today = datetime.now()

        user = kwargs.get('user')
        if user and (user.created_at.year == today.year):
            start_month = user.created_at.month

        except_months = [8, 12]
        return len([i for i in xrange(start_month, today.month + 1)
                    if i not in except_months])


class VacationType(Base):
    """
    Describe allowed type of vacation to request
    """
    name = Column(Unicode(255), nullable=False)

    countries = relationship(Countries, secondary=vacation_type__country,
                             lazy='joined', backref='vacation_type')

    _vacation_classes = {}

    # save internal map of loaded module classes
    for subclass in BaseVacation.__subclasses__():
        _vacation_classes[subclass.name] = subclass

    @classmethod
    def by_name(cls, session, name):
        """
        Get a vacation type from a given name.
        """
        return cls.first(session, where=(cls.name == name,))

    @classmethod
    def by_country(cls, session, country):
        """
        Get vacation type from a given country.
        """
        ctry = Countries.by_name(session, country)
        return cls.find(session, where=(cls.countries.contains(ctry),),
                        order_by=cls.id)

    @classmethod
    def by_name_country(cls, session, name, country, user=None):
        """
        Return allowed count of vacations per name and country
        """
        ctry = Countries.by_name(session, country)
        vac = cls.first(session, where=(cls.countries.contains(ctry),
                                        cls.name == name), order_by=cls.id)

        return (cls._vacation_classes[vac.name].acquired(user=user)
                if vac else None)


class Request(Base):
    """
    Describe a user request for vacation.
    """

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
    # actor who performed last action on request
    last_action_user_id = Column(Integer, nullable=True)
    # store caldav ics url
    ics_url = Column(UnicodeText())

    notified = Column(Boolean, default=False)
    user_id = Column('user_id', ForeignKey(User.id))
    user = relationship(User, backref='requests')

    def update_status(self, status):
        """ Reset notified flag when changing status """
        self.status = status
        self.notified = False

    def flag_error(self, message):
        """ Set request in ERROR and assign message """
        self.status = 'ERROR'
        self.message = message

    @classmethod
    def by_manager(cls, session, manager, count=None):
        """
        Get requests for users under given manager.
        """
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
        """
        Get requests for users under given manager.
        """
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
        """
        Get requests for given user.
        """
        # we only want to display less than 3 months data
        date_limit = datetime.now() - timedelta(days=90)
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status != 'CANCELED',
                               cls.date_from >= date_limit,),
                        count=count,
                        order_by=(cls.user_id, cls.date_from.desc()))

    @classmethod
    def by_user_future(cls, session, user, count=None):
        """
        Get requests for given user in the future.
        """
        return cls.find(session,
                        where=(cls.user_id == user.id,
                               cls.status != 'CANCELED',
                               cls.date_from >= datetime.now(),),
                        count=count,
                        order_by=(cls.user_id, cls.date_from.desc()))

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
        # we only want to display less than 3 months data
        date_limit = datetime.now() - timedelta(days=90)
        return cls.find(session,
                        where=(cls.status != 'CANCELED',
                               cls.date_from >= date_limit,),
                        count=count,
                        order_by=cls.user_id)

    @classmethod
    def all_for_admin_per_country(cls, session, country, count=None):
        """
        Get all requests manageable by admin per country.
        """
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
                        order_by=cls.user_id)

    @classmethod
    def in_conflict_manager(cls, session, req, count=None):
        """
        Get all requests conflicting on dates with given request,
        and with common user manager.
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
                        order_by=cls.user_id)

    @classmethod
    def in_conflict_ou(cls, session, req, count=None):
        """
        Get all requests conflicting on dates with given request,
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
                        order_by=cls.user_id)

    @classmethod
    def in_conflict(cls, session, req, count=None):
        """
        Get all requests conflicting on dates with given request.
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
        date = date.replace(month=month, year=year)
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
        """ Retrieve future validated requests per user """
        end_statement = ''
        if end_date:
            end_statement = """
                AND (date_from <= '%(end_date)s'
                    OR (date_from > '%(end_date)s'
                        AND date_to < '%(end_date)s'))
            """ % {'end_date': end_date}

        future_requests = session.execute("""
            SELECT
                request.user_id,
                sum(request.days)
            FROM
                request
            INNER JOIN "user" on "user".id = request.user_id
            WHERE
                (date_from >= NOW()
                    OR (date_from < NOW() AND date_to >= NOW()))
                %s
                AND vacation_type_id = 1
                AND status='APPROVED_ADMIN'
            GROUP BY user_id
            ORDER BY user_id;
            """ % end_statement)

        ret = {}
        for user_id, total in future_requests:
            ret[user_id] = total

        return ret

    @classmethod
    def get_today(cls, session):
        """
        Get all requests valid for current day
        """
        from datetime import datetime
        date = datetime.now().date()
        return cls.find(session,
                        join=(cls.user),
                        where=(cls.date_from <= date,
                               cls.date_to >= date,
                               cls.status == 'APPROVED_ADMIN',),
                        order_by=cls.user_id)

    @property
    def type(self):
        """
        Get name of chosen vacation type.
        """
        return _(self.vacation_type.name, self.user.country)

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
        label = ' %s' % self.label if self.label else ''
        return ('%s - %.1f %s%s' %
                (self.user.name, self.days, self.type, label))

    @property
    def summarycsv(self):
        """
        Get a string representation in csv format of a request.
        """
        # name, datefrom, dateto, number of days, type of days, label
        label = '%s' % self.label if self.label else ''
        return ('%s,%s,%s,%s,%.1f,%s,%s' %
                (self.user.lastname,
                 self.user.firstname,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y'),
                 self.days,
                 self.type,
                 label))

    @property
    def summarymail(self):
        """
        Get a short string representation of a request, for mail summary.
        """
        label = ' %s' % self.label if self.label else ''
        return ('%s: %s - %s (%.1f %s%s)' %
                (self.user.name,
                 self.date_from.strftime('%d/%m/%Y'),
                 self.date_to.strftime('%d/%m/%Y'),
                 self.days,
                 self.type,
                 label))

    def add_to_cal(self, caldav_url):
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
            self.flag_error(str(err))

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and hasattr(self, 'id')
            and hasattr(other, 'id')
            and self.id == other.id)

    def __ne__(self, other):
        return (
            isinstance(other, self.__class__)
            and hasattr(self, 'id')
            and hasattr(other, 'id')
            and self.id != other.id)


class PasswordRecovery(Base):
    """
    Describe password recovery attempts
    """
    hash = Column(Unicode(255), nullable=False, unique=True)
    date_end = Column(DateTime, nullable=False)
    user_id = Column('user_id', ForeignKey(User.id), nullable=False)
    user = relationship(User, backref='recovery')

    @classmethod
    def by_hash(cls, session, hash):
        """
        Get a recovery entry from a given hash.
        """
        return cls.first(session, where=(cls.hash == hash,))

    @property
    def expired(self):
        """
        Check if a recovery entry have expired.
        """
        from datetime import datetime
        return self.date_end < datetime.now()


class Sudoer(Base):
    """
    To allow a user to have access to another user interface
    """
    source_id = Column(Integer, nullable=False)
    target_id = Column(Integer, nullable=False)

    @classmethod
    def alias(cls, session, user):
        targets = cls.find(session, where=(cls.source_id == user.id,))
        if targets:
            return [User.by_id(session, target.target_id)
                    for target in targets]
        return []

    @classmethod
    def list(cls, session):
        return cls.find(session, order_by=cls.source_id)
