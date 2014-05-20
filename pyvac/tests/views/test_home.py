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
                              u'pyvac']))
        self.assertEqual(len(view[u'types']), 2)

    def test_render_country_ok(self):
        self.config.testing_securitypolicy(userid=u'manager3',
                                           permissive=True)
        from pyvac.views import Home
        view = Home(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'matched_route', u'types', u'csrf_token',
                              u'pyvac']))
        self.assertEqual(len(view[u'types']), 1)
