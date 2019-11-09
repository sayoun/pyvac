from pyvac.tests import case


class AccountTestCase(case.UnauthenticatedViewTestCase):

    def setUp(self):
        super(AccountTestCase, self).setUp()
        import uuid
        from pyvac.models import User, Group, Countries
        fr_country = Countries.by_name(self.session, 'fr')
        self.account_login = str(uuid.uuid4())
        u = User(login=self.account_login, password='secret',
                 _country=fr_country)
        u.groups.append(Group.by_name(self.session, 'user'))
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

        self.assertEqual(view['came_from'], 'http://pyvac.example.net')

    def test_login_ok(self):
        from pyvac.views.credentials import Login
        request = self.create_request({'submit': '1',
                                       'login': self.account_login,
                                       'password': 'secret',
                                       })
        view = Login(request)()
        self.assertIsRedirect(view)

    def test_logout_ok(self):
        from pyvac.views.credentials import Logout
        request = self.create_request()
        view = Logout(request)()
        self.assertIsRedirect(view)


class SudoTestCase(case.ViewTestCase):

    def test_login_sudo_ok(self):
        from pyvac.views.credentials import Login
        request = self.create_request({'submit': '1',
                                       'login': 'janedoe',
                                       'password': 'changeme',
                                       })
        view = Login(request)()
        self.assertTrue(view.location.endswith('/sudo'))
        self.assertIsRedirect(view)

    def test_login_sudo_nope_ok(self):
        from pyvac.views.credentials import Login
        request = self.create_request({'submit': '1',
                                       'login': 'jdoe',
                                       'password': 'changeme',
                                       })
        view = Login(request)()
        self.assertFalse(view.location.endswith('/sudo'))
        self.assertIsRedirect(view)

    def test_sudo_view_ok(self):
        self.config.testing_securitypolicy(userid='janedoe',
                                           permissive=True)
        from pyvac.views.credentials import Sudo
        view = Sudo(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['user', 'pyvac']))
        self.assertEqual(len(view['pyvac']['sudoers']), 2)

    def test_sudo_continue_ok(self):
        self.config.testing_securitypolicy(userid='janedoe',
                                           permissive=True,
                                           remember_result={'login': 'admin'})
        from pyvac.views.credentials import Sudo
        view = Sudo(self.create_request({'continue': '1', 'sudo': 1},
                                        post='blah'))()
        self.assertTrue(view.location.endswith('/home'))
        self.assertTrue(('login', 'admin') in view.headerlist)

    def test_sudo_continue_self_ok(self):
        self.config.testing_securitypolicy(userid='janedoe',
                                           permissive=True,
                                           remember_result={'login': 'admin'})
        from pyvac.views.credentials import Sudo
        view = Sudo(self.create_request({'continue': '1', 'sudo': 6},
                                        post='blah'))()
        self.assertTrue(view.location.endswith('/home'))
        self.assertFalse(('login', 'admin') in view.headerlist)
