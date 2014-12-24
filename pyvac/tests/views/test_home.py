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
                              u'pyvac', u'holidays', u'sudo_users']))
        self.assertEqual(len(view[u'types']), 2)

    def test_render_country_ok(self):
        self.config.testing_securitypolicy(userid=u'manager3',
                                           permissive=True)
        from pyvac.views import Home
        view = Home(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'matched_route', u'types', u'csrf_token',
                              u'pyvac', u'holidays', u'sudo_users']))
        self.assertEqual(len(view[u'types']), 1)

    def test_render_user_rtt_ok(self):
        self.config.testing_securitypolicy(userid=u'jdoe',
                                           permissive=True)
        from pyvac.views import Home
        view = Home(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'matched_route', u'types', u'csrf_token',
                              u'pyvac', u'holidays', u'sudo_users']))
        self.assertEqual(len(view[u'types']), 2)
        view_user = view['pyvac']['user']
        self.assertTrue(view_user.rtt)
        expected = {'allowed': 10, 'left': 9.0, 'state': 'warning',
                    'taken': 1.0, 'year': 2014}
        self.assertEqual(view_user.rtt, expected)
