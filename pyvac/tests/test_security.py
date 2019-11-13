from .case import UnauthenticatedViewTestCase


class RootFactoryTestCase(UnauthenticatedViewTestCase):

    def test_get_acl_admin(self):
        from pyvac.security import RootFactory
        root = RootFactory(self.create_request())
        self.assertEqual(set(root.__acl__),
                         set([
                             ('Allow', 'admin', 'admin_view'),
                             ('Allow', 'admin', 'manager_view'),
                             ('Allow', 'admin', 'user_view'),
                             ('Allow', 'admin', 'sudo_view'),
                             ('Allow', 'manager', 'manager_view'),
                             ('Allow', 'manager', 'user_view'),
                             ('Allow', 'manager', 'sudo_view'),
                             ('Allow', 'user', 'user_view'),
                             ('Allow', 'sudoer', 'sudo_view')]))


class GroupFinderTestCase(UnauthenticatedViewTestCase):

    def test_admin_groups(self):
        from pyvac.security import groupfinder
        self.assertEqual(set(groupfinder('admin', self.create_request())),
                         set(['admin']))

    def test_manager_groups(self):
        from pyvac.security import groupfinder
        self.assertEqual(set(groupfinder('manager1', self.create_request())),
                         set(['manager']))

    def test_user_groups(self):
        from pyvac.security import groupfinder
        self.assertEqual(set(groupfinder('jdoe', self.create_request())),
                         set(['user']))
