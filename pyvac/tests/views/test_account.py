from pyvac.tests import case


class AccountTestCase(case.ViewTestCase):

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

    def test_get_list_ok(self):
        from pyvac.models import User
        from pyvac.views.account import List
        view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['pyvac', 'user_count', 'users', 'users_teams',
                              'use_ldap', 'ldap_info', 'active_users']))
        self.assertEqual(view['user_count'], 8)
        self.assertEqual(len(view['users']), 8)
        self.assertIsInstance(view['users'][0], User)

    def test_get_create_ok(self):
        from pyvac.views.account import Create
        from pyvac.models import User, Group
        view = Create(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['errors', 'groups', 'pyvac', 'user',
                              'managers', 'csrf_token', 'use_ldap',
                              'countries', 'partial_time_tooltip']))

        self.assertEqual(view['errors'], [])
        groups = [g for g in view['groups']]
        self.assertEqual(len(groups), 4)
        self.assertIsInstance(groups[0], Group)
        self.assertIsInstance(view['user'], User)
        self.assertIsNone(view['user'].id)
        self.assertIsNone(view['user'].login)

    def test_post_create_ok(self):
        from pyvac.views.account import Create
        from pyvac.models import User
        view = Create(self.create_request({'form.submitted': u'1',
                                           'user.login': u'dummy_new',
                                           'user.password': u'secret',
                                           'user.firstname': u'',
                                           'user.lastname': u'',
                                           'user.email': u'me@me.me',
                                           'confirm_password': u'secret',
                                           'groups': [u'1', u'2']
                                           }))()
        self.assertIsRedirect(view)
        self.account_todelete.append(User.by_login(self.session,
                                                   u'dummy_new').id)

    def test_post_create_wrong_pass_ko(self):
        from pyvac.views.account import Create
        from pyvac.models import User, Group
        view = Create(self.create_request({'form.submitted': u'1',
                                           'user.login': u'dummy_new',
                                           'user.password': u'secret',
                                           'user.firstname': u'',
                                           'user.lastname': u'',
                                           'user.email': u'me@me.me',
                                           'confirm_password': u'secret2',
                                           'groups': [u'1', u'2']
                                           }))()
        self.assertEqual(set(view.keys()),
                         set(['errors', 'groups', 'pyvac', 'user',
                              'managers', 'csrf_token', 'use_ldap',
                              'countries', 'partial_time_tooltip']))

        self.assertEqual(view['errors'], [u'passwords do not match'])
        groups = [g for g in view['groups']]
        self.assertEqual(len(groups), 4)
        self.assertIsInstance(groups[0], Group)
        self.assertIsInstance(view['user'], User)
        self.assertIsNone(view['user'].id)
        self.assertIsNone(view['user'].login)

    def test_get_edit_ok(self):
        from pyvac.views.account import Edit
        from pyvac.models import User, Group
        view = Edit(self.create_request(matchdict={'user_id': self.account_id
                                                   }))()
        self.assertEqual(set(view.keys()),
                         set(['errors', 'groups', 'pyvac', 'user',
                              'managers', 'csrf_token', 'use_ldap',
                              'countries', 'partial_time_tooltip']))
        self.assertEqual(view['errors'], [])
        groups = [g for g in view['groups']]
        self.assertEqual(len(groups), 4)
        self.assertIsInstance(groups[0], Group)
        self.assertIsInstance(view['user'], User)
        self.assertEqual(view['user'].id, self.account_id)
        self.assertEqual(view['user'].login, self.account_login)

    def test_post_edit_ok(self):
        from pyvac.views.account import Edit
        from pyvac.models import User
        view = Edit(self.create_request({'form.submitted': '1',
                                         'user.login': u'dummy_edited',
                                         'user.firstname': u'',
                                         'user.lastname': u'',
                                         'user.email': u'me@me.me',
                                         'groups': [u'1']
                                         },
                                        matchdict={'user_id': self.account_id
                                                   }))()
        self.assertIsRedirect(view)
        self.session.flush()
        user = User.by_id(self.session, self.account_id)
        self.assertEqual(user.login, u'dummy_edited')
        self.assertEqual([g.id for g in user.groups], [1])

    def test_post_edit_first_last_names_ok(self):
        from pyvac.views.account import Edit
        from pyvac.models import User
        view = Edit(self.create_request({'form.submitted': '1',
                                         'user.login': u'dummy_edited',
                                         'user.firstname': u'foo',
                                         'user.lastname': u'bar',
                                         'user.email': u'me@me.me',
                                         'groups': [u'1']
                                         },
                                        matchdict={'user_id': self.account_id
                                                   }))()
        self.assertIsRedirect(view)
        self.session.flush()
        user = User.by_id(self.session, self.account_id)
        self.assertEqual(user.login, u'dummy_edited')
        self.assertEqual(user.firstname, u'foo')
        self.assertEqual(user.lastname, u'bar')
        self.assertEqual([g.id for g in user.groups], [1])

    def test_get_delete_ok(self):
        from pyvac.views.account import Delete
        from pyvac.models import User
        view = Delete(self.create_request(matchdict={'user_id': self.account_id
                                                     }))()
        self.assertEqual(set(view.keys()),
                         set(['pyvac', 'user']))
        self.assertIsInstance(view['user'], User)
        self.assertEqual(view['user'].id, self.account_id)
        self.assertEqual(view['user'].login, self.account_login)

    def test_post_delete_ok(self):
        from pyvac.views.account import Delete
        from pyvac.models import User
        view = Delete(self.create_request({'form.submitted': '1',
                                           },
                                          matchdict={'user_id': self.account_id
                                                     },))()
        self.assertIsRedirect(view)
        account = User.by_id(self.session, self.account_id)
        self.assertIsNone(account)
        self.account_todelete = []
