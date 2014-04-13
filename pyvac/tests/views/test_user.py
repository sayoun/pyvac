from pyvac.tests import case


class AccountTestCase(case.ViewAdminTestCase):

    def test_update_get(self):
        from pyvac.views.user import Edit
        view = Edit(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['csrf_token', 'pyvac', 'user', 'errors',
                              'use_ldap']))
        self.assertEqual(view['user'].login, u'admin')

    def test_update_password(self):
        from pyvac.views.user import ChangePassword as ChangePwd
        view = ChangePwd(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['csrf_token', 'pyvac', 'user', 'errors',
                              'use_ldap']))
        self.assertEqual(view['user'].login, u'admin')

    def test_update_post_ok(self):
        from pyvac.models import User
        from pyvac.views.user import Edit
        view = Edit(self.create_request({'form.submitted': u'1',
                                         'user.login': u'root',
                                         'user.firstname': u'Admin',
                                         'user.lastname': u'Istrator',
                                         }))()
        self.assertIsRedirect(view)
        self.session.flush()
        admin = User.by_credentials(self.session, u'root', u'changeme')
        self.assertIsInstance(admin, User)
        self.assertEqual(admin.login, u'root')
        self.assertEqual(admin.firstname, u'Admin')
        self.assertEqual(admin.lastname, u'Istrator')
        admin.login = u'admin'
        admin.password = u'changeme'
        admin.firstname = None
        admin.lastname = None
        self.session.add(admin)

    def test_change_password_post_ok(self):
        from pyvac.models import User
        from pyvac.views.user import ChangePassword as ChangePwd
        ChangePwd(self.create_request({'form.submitted': u'1',
                                       'current_password': u'changeme',
                                       'user.password': u'newpassw',
                                       'confirm_password': u'newpassw',
                                       }))()
        admin = User.by_credentials(self.session, u'admin', u'newpassw')
        self.assertIsInstance(admin, User)
        admin.password = u'changeme'
        self.session.add(admin)

    def test_change_password_post_ko_not_matched(self):
        from pyvac.models import User
        from pyvac.views.user import ChangePassword as ChangePwd
        view = ChangePwd(self.create_request({'form.submitted': u'1',
                                              'current_password': u'CHANGEME',
                                              'user.password': u'newpassw',
                                              'confirm_password': u'NEWPASSW',
                                              }))()
        self.assertEqual(view['errors'],
                         [u'current password is not correct',
                          u'passwords do not match'])
        admin = User.by_credentials(self.session, u'admin', u'changeme')
        self.assertIsInstance(admin, User)

    def test_change_password_post_ko_unchanged(self):
        from pyvac.models import User
        from pyvac.views.user import ChangePassword as ChangePwd
        view = ChangePwd(self.create_request({'form.submitted': u'1',
                                              'current_password': u'changeme',
                                              'user.password': u'changeme',
                                              'confirm_password': u'changeme',
                                              }))()
        self.assertEqual(view['errors'],
                         [u'password is inchanged'])
        admin = User.by_credentials(self.session, u'admin', u'changeme')
        self.assertIsInstance(admin, User)
