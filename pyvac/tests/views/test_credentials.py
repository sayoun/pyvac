from pyvac.tests import case


class AccountTestCase(case.UnauthenticatedViewTestCase):

    def setUp(self):
        super(AccountTestCase, self).setUp()
        import uuid
        from pyvac.models import User, Group, Countries
        fr_country = Countries.by_name(self.session, u'fr')
        self.account_login = unicode(uuid.uuid4())
        u = User(login=self.account_login, password=u'secret',
                 _country=fr_country)
        u.groups.append(Group.by_name(self.session, u'user'))
        self.session.add(u)
        self.session.flush()
        self.account_id = u.id
        self.account_todelete = [self.account_id]

    def tearDown(self):
        from pyvac.models import User
        for id in self.account_todelete:
            u = User.by_id(self.session, id)
            self.session.delete(u)
        super(AccountTestCase, self).tearDown()

    def test_login_unknown(self):
        from pyvac.views.credentials import Login
        request = self.create_request()
        view = Login(request)()
        self.assertEqual(set(view.keys()),
                         set(['pyvac', 'csrf_token', 'came_from']))

        self.assertEqual(view['came_from'], u'http://pyvac.example.net')

    def test_login_ok(self):
        from pyvac.views.credentials import Login
        request = self.create_request({'submit': u'1',
                                       'login': self.account_login,
                                       'password': u'secret',
                                       })
        view = Login(request)()
        self.assertIsRedirect(view)

    def test_logout_ok(self):
        from pyvac.views.credentials import Logout
        request = self.create_request()
        view = Logout(request)()
        self.assertIsRedirect(view)
