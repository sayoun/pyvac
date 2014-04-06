from .case import UnauthenticatedViewTestCase


class RootFactoryTestCase(UnauthenticatedViewTestCase):

    def test_get_acl_admin(self):
        from pyvac.security import RootFactory
        root = RootFactory(self.create_request())
        self.assertEqual(set(root.__acl__),
                         set([
                             ('Allow', u'admin', u'admin_view'),
                             ('Allow', u'admin', u'manager_view'),
                             ('Allow', u'admin', u'user_view'),
                             ('Allow', u'manager', u'manager_view'),
                             ('Allow', u'manager', u'user_view'),
                             ('Allow', u'user', u'user_view')]))


class GroupFinderTestCase(UnauthenticatedViewTestCase):

    def test_admin_groups(self):
        from pyvac.security import groupfinder
        self.assertEqual(set(groupfinder(u'admin', self.create_request())),
                         set([u'admin']))

    def test_manager_groups(self):
        from pyvac.security import groupfinder
        self.assertEqual(set(groupfinder(u'manager1', self.create_request())),
                         set([u'manager']))

    def test_user_groups(self):
        from pyvac.security import groupfinder
        self.assertEqual(set(groupfinder(u'jdoe', self.create_request())),
                         set([u'user']))

