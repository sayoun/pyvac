from datetime import datetime
from freezegun import freeze_time
from dateutil.relativedelta import relativedelta
from mock import patch, PropertyMock

from .case import ModelTestCase


class GroupTestCase(ModelTestCase):

    def test_by_name(self):
        from pyvac.models import Group
        grp = Group.by_name(self.session, u'admin')
        self.assertIsInstance(grp, Group)
        self.assertEqual(grp.name, u'admin')


class UserTestCase(ModelTestCase):

    def test_by_login_ko_mirrored(self):
        from pyvac.models import User
        user = User.by_login(self.session, u'johndo')
        self.assertEqual(user, None)

    def test_by_credentials_ko_unexists(self):
        from pyvac.models import User
        user = User.by_credentials(self.session, u'u404', u"' OR 1 = 1 #")
        self.assertEqual(user, None)

    def test_by_credentials_ko_mirrored(self):
        from pyvac.models import User
        user = User.by_credentials(self.session, u'johndo', '')
        self.assertEqual(user, None)

    def test_by_credentials_ko_password(self):
        from pyvac.models import User
        user = User.by_credentials(self.session, u'admin', 'CHANGEME')
        self.assertIsNone(user)

    def test_by_credentials_ok(self):
        from pyvac.models import User
        user = User.by_credentials(self.session, u'jdoe', u'changeme')
        self.assertIsInstance(user, User)
        self.assertEqual(user.login, u'jdoe')
        self.assertEqual(user.name, u'John Doe')
        self.assertEqual(user.role, u'user')

    def test_hash_password(self):
        from pyvac.models import User
        u = User(login=u'test_password', password=u'secret')
        self.assertNotEqual(u.password, u'secret', 'password must be hashed')

    def test_by_role(self):
        from pyvac.models import User
        admins = User.by_role(self.session, 'admin')
        self.assertEqual(len(admins), 1)

    def test_get_admin_by_country(self):
        from pyvac.models import User
        admin = User.get_admin_by_country(self.session, u'fr')
        self.assertEqual(admin.login, u'admin')
        self.assertEqual(admin.country, u'fr')

    def test_by_country(self):
        from pyvac.models import User
        country_id = 1
        users = User.by_country(self.session, country_id)
        self.assertEqual(len(users), 5)
        country_id = 3
        users = User.by_country(self.session, country_id)
        self.assertEqual(len(users), 1)

    def test_get_rtt_usage(self):
        from pyvac.models import User
        user = User.by_login(self.session, u'jdoe')
        self.assertIsInstance(user, User)
        self.assertEqual(user.login, u'jdoe')
        self.assertEqual(user.name, u'John Doe')
        self.assertEqual(user.role, u'user')
        with freeze_time('2014-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            expected = {'allowed': 10, 'left': 9.5, 'state': 'warning',
                        'taken': 0.5, 'year': 2014}
            self.assertEqual(user.get_rtt_usage(self.session), expected)
            # no RTT for us country
            user = User.by_login(self.session, u'manager3')
            self.assertIsInstance(user, User)
            self.assertEqual(user.country, u'us')
            self.assertIsNone(user.get_rtt_usage(self.session))

    def test_get_rtt_taken_year(self):
        from pyvac.models import User
        user = User.by_login(self.session, u'jdoe')
        self.assertIsInstance(user, User)
        self.assertEqual(user.login, u'jdoe')
        self.assertEqual(user.name, u'John Doe')
        self.assertEqual(user.role, u'user')

        self.assertEqual(user.get_rtt_taken_year(self.session, 2014), 0.5)
        # no RTT for us country
        user = User.by_login(self.session, u'manager3')
        self.assertIsInstance(user, User)
        self.assertEqual(user.country, u'us')
        self.assertEqual(user.get_rtt_taken_year(self.session, 2014), 0)


class RequestTestCase(ModelTestCase):

    def test_by_manager(self):
        from pyvac.models import User, Request
        manager1 = User.by_login(self.session, u'manager1')
        with freeze_time('2015-03-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            requests = Request.by_manager(self.session, manager1)
        self.assertEqual(len(requests), 10)
        # take the first
        request = requests.pop()
        self.assertIsInstance(request, Request)

    def test_by_user(self):
        from pyvac.models import User, Request
        user1 = User.by_login(self.session, u'jdoe')
        with freeze_time('2015-08-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            requests = Request.by_user(self.session, user1)
        self.assertEqual(len(requests), 8)
        # take the first
        request = requests[-1]
        self.assertIsInstance(request, Request)
        self.assertEqual(request.days, 5)
        self.assertEqual(request.type, u'CP')
        self.assertEqual(request.status, u'PENDING')
        self.assertEqual(request.notified, False)
        self.assertEqual(request.date_from, datetime(2015, 4, 10, 0, 0))
        self.assertEqual(request.date_to, datetime(2015, 4, 14, 0, 0))

    def test_by_user_outdated(self):
        from pyvac.models import User, Request
        user1 = User.by_login(self.session, u'jdoe')
        with freeze_time('2015-08-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            requests = Request.by_user(self.session, user1)
        self.assertEqual(len(requests), 8)

        outdated = Request.by_id(self.session, 7)
        self.assertIsInstance(outdated, Request)
        self.assertEqual(outdated.user, user1)
        self.assertFalse(outdated in requests)

    def test_by_status_not_notified_ko(self):
        from pyvac.models import Request
        nb_requests = Request.by_status(self.session, u'ACCEPTED_MANAGER',
                                        count=True)
        self.assertEqual(nb_requests, 0)

    def test_by_status_not_notified_ok(self):
        from pyvac.models import Request
        requests = Request.by_status(self.session, u'ACCEPTED_MANAGER',
                                     notified=True)
        self.assertEqual(len(requests), 2)
        # take the first
        request = requests[0]
        self.assertIsInstance(request, Request)
        self.assertEqual(request.days, 5)
        self.assertEqual(request.type, u'RTT')
        self.assertEqual(request.status, u'ACCEPTED_MANAGER')
        self.assertEqual(request.notified, True)
        self.assertEqual(request.date_from, datetime(2015, 4, 24, 0, 0))
        self.assertEqual(request.date_to, datetime(2015, 4, 28, 0, 0))

    def test_all_for_admin(self):
        from pyvac.models import Request
        with freeze_time('2014-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            nb_requests = Request.all_for_admin(self.session, count=True)
        self.assertEqual(nb_requests, 17)

    def test_in_conflict_manager(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 1)
        self.assertIsInstance(req, Request)
        nb_conflicts = Request.in_conflict_manager(self.session, req,
                                                   count=True)
        self.assertEqual(nb_conflicts, 1)

    def test_in_conflict_ou(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 1)
        self.assertIsInstance(req, Request)
        nb_conflicts = Request.in_conflict_ou(self.session, req, count=True)
        self.assertEqual(nb_conflicts, 1)

    def test_in_conflict(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 1)
        self.assertIsInstance(req, Request)
        nb_conflicts = Request.in_conflict(self.session, req, count=True)
        self.assertEqual(nb_conflicts, 1)

    def test_get_by_month(self):
        from pyvac.models import Request
        month = 8
        year = 2011
        country = u'fr'
        requests = Request.get_by_month(self.session, country, month, year)
        self.assertEqual(len(requests), 1)

    def test_summary(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 1)
        self.assertIsInstance(req, Request)
        self.assertEqual(req.summary, u'John Doe: 10/04/2015 - 14/04/2015')

    def test_summarycal(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 1)
        self.assertIsInstance(req, Request)
        self.assertEqual(req.summarycal, u'John Doe - 5.0 CP')

    def test_summarycsv(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 1)
        self.assertIsInstance(req, Request)
        msg = u'1337,Doe,John,10/04/2015,14/04/2015,5.0,CP,,'
        self.assertEqual(req.summarycsv, msg)

    def test_summarycsv_label(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 6)
        self.assertIsInstance(req, Request)
        msg = u'1337,Doe,John,24/08/2011,24/08/2011,0.5,RTT,AM,'
        self.assertEqual(req.summarycsv, msg)

    def test_summarycsv_message(self):
        from pyvac.models import Request
        req = Request.by_id(self.session, 14)
        self.assertIsInstance(req, Request)
        msg = (u",Doe,Jane,13/06/2016,13/06/2016,1.0,Exceptionnel,,"
               "I need to see Star Wars, I'm a huge fan")
        self.assertEqual(req.summarycsv, msg)


class VacationTypeTestCase(ModelTestCase):

    def test_by_country_ok(self):
        from pyvac.models import User, VacationType
        manager3 = User.by_login(self.session, u'manager3')
        vac_types = VacationType.by_country(self.session, manager3.country)
        self.assertEqual(len(vac_types), 5)
        # take the first
        vac_type = vac_types.pop()
        self.assertIsInstance(vac_type, VacationType)

    def test_by_name_country_no_rtt_ko(self):
        from pyvac.models import User, VacationType
        manager3 = User.by_login(self.session, u'manager3')
        vac = VacationType.by_name_country(self.session, u'RTT',
                                           manager3.country)
        self.assertIsNone(vac)

    def test_by_name_country_rtt_ok(self):
        from pyvac.models import User, VacationType
        jdoe = User.by_login(self.session, u'jdoe')
        with freeze_time('2014-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            kwargs = {'session': self.session,
                      'name': u'RTT', 'country': jdoe.country}
            vac = VacationType.by_name_country(**kwargs)
            self.assertEqual(vac.acquired(**kwargs), 10)

    def test_by_name_country_rtt_truncated_ok(self):
        from pyvac.models import User, VacationType
        jdoe = User.by_login(self.session, u'jdoe')
        jdoe.created_at = datetime(2014, 9, 13)
        with freeze_time('2014-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            kwargs = {'session': self.session,
                      'name': u'RTT', 'country': jdoe.country,
                      'user': jdoe}
            vac = VacationType.by_name_country(**kwargs)
            self.assertEqual(vac.acquired(**kwargs), 3)

    def test_sub_classes_ok(self):
        from pyvac.models import VacationType
        self.assertEqual(VacationType._vacation_classes.keys(),
                         [u'CP_lu', u'CP_fr', u'RTT_fr', u'Compensatoire_lu'])

    def test_sub_classes_rtt_ok(self):
        from pyvac.models import VacationType
        sub = VacationType._vacation_classes[u'RTT_fr']
        with freeze_time('2014-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            self.assertEqual(sub.acquired(), 10)
        with freeze_time('2014-08-15',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            self.assertEqual(sub.acquired(), 7)

    def test_visibility_ok(self):
        from pyvac.models import VacationType
        vac_type = VacationType.by_id(self.session, 5)
        self.assertEqual(vac_type.visibility, 'admin')
        vac_type = VacationType.by_id(self.session, 1)
        self.assertEqual(vac_type.visibility, None)


class CPVacationTestCase(ModelTestCase):

    def test_lu_holidays_recovered(self):
        from pyvac.models import User
        user = User.by_login(self.session, u'sarah.doe')
        self.assertIsInstance(user, User)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mockfoo:
            mockfoo.return_value = datetime.now() - relativedelta(months=5)
            to_recover = user.get_lu_holiday(datetime(2017, 1, 25, 0, 0))
            # there is a holiday on 25 dec. which should be available
            self.assertEqual(to_recover, [datetime(2016, 12, 25, 0, 0),
                                          datetime(2017, 1, 1, 0, 0)])

    def test_lu_validate_request(self):
        from pyvac.models import CPLUVacation, CompensatoireVacation, User
        user = User.by_login(self.session, u'sarah.doe')
        self.assertIsInstance(user, User)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=5)
            pool = user.get_cp_usage(self.session)
            days = 3
            date_from = datetime.now()
            date_to = datetime.now() + relativedelta(days=3)
            err = CPLUVacation.validate_request(user, pool, days,
                                                date_from, date_to)
            self.assertEqual(err, None)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=2)
            pool = user.get_cp_usage(self.session)
            days = 3
            date_from = datetime.now()
            date_to = datetime.now() + relativedelta(days=3)
            err = CPLUVacation.validate_request(user, pool, days,
                                                date_from, date_to)
            msg = 'You need 3 months of seniority before using your CP'
            self.assertEqual(err, msg)

        with freeze_time('2016-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime.now() - relativedelta(months=5) # noqa
                pool = user.get_cp_usage(self.session)
                days = 3
                date_from = datetime.now().replace(year=datetime.now().year + 1) # noqa
                date_to = date_from + relativedelta(days=3)
                err = CPLUVacation.validate_request(user, pool, days,
                                                    date_from, date_to)
                msg = 'CP can only be used until 31/03/%d.' % pool['acquis']['expire'].year # noqa
                self.assertEqual(err, msg)

        with freeze_time('2016-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime.now() - relativedelta(months=5) # noqa
                pool = user.get_cp_usage(self.session)
                days = 250
                date_from = datetime.now()
                date_to = datetime.now() + relativedelta(days=3)
                err = CPLUVacation.validate_request(user, pool, days,
                                                    date_from, date_to)
                msg = 'You only have 164 CP to use.'
                self.assertEqual(err, msg)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=5)
            pool = user.get_cp_usage(self.session)
            # lower the amount of pool left
            pool['acquis']['left'] = 0
            pool['restant']['left'] = 0
            days = 20
            date_from = datetime.now()
            date_to = datetime.now() + relativedelta(days=3)
            err = CPLUVacation.validate_request(user, pool, days,
                                                date_from, date_to)
            msg = 'No CP left to take.'
            self.assertEqual(err, msg)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=5)
            days = 3
            date_from = datetime(2016, 12, 25)
            err = CompensatoireVacation.validate_request(user, None, days,
                                                         date_from, None)
            msg = ('You can only use 1 Compensatory holiday at a time, '
                   'for a full day.')
            self.assertEqual(err, msg)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=5)
            days = 0.5
            date_from = datetime(2016, 12, 25)
            err = CompensatoireVacation.validate_request(user, None, days,
                                                         date_from, None)
            msg = ('You can only use 1 Compensatory holiday at a time, '
                   'for a full day.')
            self.assertEqual(err, msg)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=5)
            days = 1
            date_from = datetime(2016, 12, 30)
            err = CompensatoireVacation.validate_request(user, None, days,
                                                         date_from, None)
            msg = '30/12/2016 is not a valid value for Compensatory vacation'
            self.assertEqual(err, msg)

        with freeze_time('2017-01-20',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime.now() - relativedelta(months=5)
                days = 1
                date_to = datetime(2016, 12, 20)
                date_from = datetime(2016, 12, 25)
                err = CompensatoireVacation.validate_request(user, None, days,
                                                             date_from, date_to)
                msg = 'You must request a date after 25/12/2016'
                self.assertEqual(err, msg)

        with freeze_time('2017-01-20',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime.now() - relativedelta(months=5)
                days = 1
                date_to = datetime(2017, 4, 1)
                date_from = datetime(2016, 12, 25)
                err = CompensatoireVacation.validate_request(user, None, days,
                                                             date_from, date_to)
                msg = ('You must request a date in the following 3 months '
                       'after 25/12/2016')
                self.assertEqual(err, msg)

    def test_cp_validate_request(self):
        from pyvac.models import CPVacation, User
        user = User.by_login(self.session, u'jdoe')
        self.assertIsInstance(user, User)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=7)
            pool = user.get_cp_usage(self.session)
            days = 3
            date_from = datetime.now()
            date_to = datetime.now() + relativedelta(days=3)
            err = CPVacation.validate_request(user, pool, days,
                                              date_from, date_to)
            self.assertEqual(err, None)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=7)
            pool = user.get_cp_usage(self.session)
            days = 3
            date_from = datetime.now().replace(year=datetime.now().year + 2)
            date_to = date_from + relativedelta(days=3)
            err = CPVacation.validate_request(user, pool, days,
                                              date_from, date_to)
            msg = 'CP can only be used until 31/05/%d.' % pool['acquis']['expire'].year # noqa
            self.assertEqual(err, msg)


class SudoerTestCase(ModelTestCase):

    def test_list(self):
        from pyvac.models import Sudoer
        sudoers = Sudoer.list(self.session)
        self.assertEqual(len(sudoers), 1)
        sudoer = sudoers[0]
        self.assertIsInstance(sudoer, Sudoer)
        self.assertEqual(sudoer.target_id, 1)
        self.assertEqual(sudoer.source_id, 6)

    def test_alias(self):
        from pyvac.models import Sudoer
        from pyvac.models import User
        user = User.by_login(self.session, u'janedoe')
        self.assertIsInstance(user, User)

        sudoers = Sudoer.alias(self.session, user)
        self.assertEqual(len(sudoers), 1)
        sudoer = sudoers[0]
        self.assertIsInstance(sudoer, User)

    def test_alias_ko(self):
        from pyvac.models import Sudoer
        from pyvac.models import User
        user = User.by_login(self.session, u'jdoe')
        self.assertIsInstance(user, User)

        sudoers = Sudoer.alias(self.session, user)
        self.assertEqual(sudoers, [])
