from datetime import datetime
from freezegun import freeze_time
from mock import patch, PropertyMock

from pyvac.tests import case


class HomeTestCase(case.ViewTestCase):

    def setUp(self):
        super(HomeTestCase, self).setUp()

    def tearDown(self):
        super(HomeTestCase, self).tearDown()

    def test_render_admin_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.views import Home
        view = Home(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'matched_route', u'types', u'csrf_token',
                              u'pyvac', u'holidays', u'sudo_users',
                              u'exception_info_tooltip',
                              u'recovered_info_tooltip', u'recovered_cp',
                              u'futures_approved', u'futures_pending',
                              u'futures_breakdown']))
        self.assertEqual(len(view[u'types']), 6)

    def test_render_country_ok(self):
        self.config.testing_securitypolicy(userid=u'manager3',
                                           permissive=True)
        from pyvac.views import Home
        view = Home(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'matched_route', u'types', u'csrf_token',
                              u'pyvac', u'holidays', u'sudo_users',
                              u'exception_info_tooltip',
                              u'recovered_info_tooltip', u'recovered_cp',
                              u'futures_approved', u'futures_pending',
                              u'futures_breakdown']))
        self.assertEqual(len(view[u'types']), 4)

    def test_render_holiday_ok(self):
        self.config.testing_securitypolicy(userid=u'manager2',
                                           permissive=True)
        from pyvac.views import Home
        with freeze_time('2015-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            view = Home(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'matched_route', u'types', u'csrf_token',
                              u'pyvac', u'holidays', u'sudo_users',
                              u'exception_info_tooltip',
                              u'recovered_info_tooltip', u'recovered_cp',
                              u'futures_approved', u'futures_pending',
                              u'futures_breakdown']))
        self.assertEqual(len(view[u'types']), 5)
        self.assertEqual(len(view[u'holidays']), 22)

    def test_render_user_rtt_ok(self):
        self.config.testing_securitypolicy(userid=u'jdoe',
                                           permissive=True)
        from pyvac.views import Home
        with freeze_time('2014-12-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime(2014, 1, 1)
                view = Home(self.create_request())()
                self.assertEqual(set(view.keys()),
                                 set([u'matched_route', u'types',
                                      u'csrf_token',
                                      u'pyvac', u'holidays', u'sudo_users',
                                      u'exception_info_tooltip',
                                      u'recovered_info_tooltip',
                                      u'recovered_cp',
                                      u'futures_approved', u'futures_pending',
                                      u'futures_breakdown']))
                self.assertEqual(len(view[u'types']), 5)
                view_user = view['pyvac']['user']
                view_user.rtt = view_user.get_rtt_usage(self.session)
                self.assertTrue(view_user.rtt)
                expected = {'allowed': 10, 'left': 9.5, 'state': 'warning',
                            'taken': 0.5, 'year': 2014}
                self.assertEqual(view_user.rtt, expected)

        with freeze_time('2011-01-02',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime(2011, 1, 1)
                view = Home(self.create_request())()
                self.assertEqual(set(view.keys()),
                                 set([u'matched_route', u'types',
                                      u'csrf_token',
                                      u'pyvac', u'holidays', u'sudo_users',
                                      u'exception_info_tooltip',
                                      u'recovered_info_tooltip',
                                      u'recovered_cp',
                                      u'futures_approved', u'futures_pending',
                                      u'futures_breakdown']))
                self.assertEqual(len(view[u'types']), 5)
                view_user = view['pyvac']['user']
                view_user.rtt = view_user.get_rtt_usage(self.session)
                self.assertTrue(view_user.rtt)
                expected = {'allowed': 1, 'left': 0.5, 'state': 'success',
                            'taken': 0.5, 'year': 2011}
                self.assertEqual(view_user.rtt, expected)

        # testing that we take count of all type of requests
        # PENDING, ACCEPTED_MANAGER, APPROVED_ADMIN
        with freeze_time('2016-05-02',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime(2016, 1, 1)
                view = Home(self.create_request())()
                self.assertEqual(set(view.keys()),
                                 set([u'matched_route', u'types',
                                      u'csrf_token',
                                      u'pyvac', u'holidays', u'sudo_users',
                                      u'exception_info_tooltip',
                                      u'recovered_info_tooltip',
                                      u'recovered_cp',
                                      u'futures_approved', u'futures_pending',
                                      u'futures_breakdown']))
                self.assertEqual(len(view[u'types']), 5)
                view_user = view['pyvac']['user']
                view_user.rtt = view_user.get_rtt_usage(self.session)
                self.assertTrue(view_user.rtt)
                expected = {'allowed': 5, 'left': 2.0, 'state': 'success',
                            'taken': 3.0, 'year': 2016}
                self.assertEqual(view_user.rtt, expected)
