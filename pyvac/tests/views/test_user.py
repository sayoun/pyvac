from pyvac.tests import case


class AccountTestCase(case.ViewAdminTestCase):

    def test_update_get(self):
        from pyvac.views.user import Edit
        view = Edit(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['csrf_token', 'pyvac', 'user', 'errors',
                              'use_ldap']))
        self.assertEqual(view['user'].login, 'admin')

    def test_update_password(self):
        from pyvac.views.user import ChangePassword as ChangePwd
        view = ChangePwd(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['csrf_token', 'pyvac', 'user', 'errors',
                              'use_ldap']))
        self.assertEqual(view['user'].login, 'admin')

    def test_update_post_ok(self):
        from pyvac.models import User
        from pyvac.views.user import Edit
        view = Edit(self.create_request({'form.submitted': '1',
                                         'user.login': 'root',
                                         'user.firstname': 'Admin',
                                         'user.lastname': 'Istrator',
                                         }))()
        self.assertIsRedirect(view)
        self.session.flush()
        admin = User.by_credentials(self.session, 'root', 'changeme')
        self.assertIsInstance(admin, User)
        self.assertEqual(admin.login, 'root')
        self.assertEqual(admin.firstname, 'Admin')
        self.assertEqual(admin.lastname, 'Istrator')
        admin.login = 'admin'
        admin.password = 'changeme'
        admin.firstname = None
        admin.lastname = None
        self.session.add(admin)

    def test_change_password_post_ok(self):
        from pyvac.models import User
        from pyvac.views.user import ChangePassword as ChangePwd
        ChangePwd(self.create_request({'form.submitted': '1',
                                       'current_password': 'changeme',
                                       'user.password': 'newpassw',
                                       'confirm_password': 'newpassw',
                                       }))()
        admin = User.by_credentials(self.session, 'admin', 'newpassw')
        self.assertIsInstance(admin, User)
        admin.password = 'changeme'
        self.session.add(admin)

    def test_change_password_post_ko_not_matched(self):
        from pyvac.models import User
        from pyvac.views.user import ChangePassword as ChangePwd
        view = ChangePwd(self.create_request({'form.submitted': '1',
                                              'current_password': 'CHANGEME',
                                              'user.password': 'newpassw',
                                              'confirm_password': 'NEWPASSW',
                                              }))()
        self.assertEqual(view['errors'],
                         ['current password is not correct',
                          'passwords do not match'])
        admin = User.by_credentials(self.session, 'admin', 'changeme')
        self.assertIsInstance(admin, User)

    def test_change_password_post_ko_unchanged(self):
        from pyvac.models import User
        from pyvac.views.user import ChangePassword as ChangePwd
        view = ChangePwd(self.create_request({'form.submitted': '1',
                                              'current_password': 'changeme',
                                              'user.password': 'changeme',
                                              'confirm_password': 'changeme',
                                              }))()
        self.assertEqual(view['errors'],
                         ['password is inchanged'])
        admin = User.by_credentials(self.session, 'admin', 'changeme')
        self.assertIsInstance(admin, User)
