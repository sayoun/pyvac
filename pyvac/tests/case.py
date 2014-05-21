

try:
    from unittest2 import TestCase  # Python2.6
except ImportError:
    from unittest import TestCase


import transaction
from webob.multidict import MultiDict
from pyramid import testing
from pyramid.httpexceptions import HTTPFound
# from pyramid.authorization import ACLAuthorizationPolicy

from mock import patch

from pyvac.models import DBSession


class ModelTestCase(TestCase):

    def setUp(self):
        transaction.begin()
        self.session = DBSession()

    def tearDown(self):
        transaction.commit()


class DummyRoute(object):
    name = 'index'


class DummyRequest(testing.DummyRequest):
    method = u'GET'
    application_url = u'http://pyvac.example.net'
    host = u'pyvac.example.net:80'
    client_addr = u'127.0.0.8'
    matched_route = DummyRoute

    def auto_translate(string, country):
        return string

    translate = auto_translate


class UnauthenticatedViewTestCase(TestCase):

    mocks = []

    def __init__(self, methodName='runTest'):
        super(UnauthenticatedViewTestCase, self).__init__(methodName)
        # pylint: disable=W0142
        self.mocks = [patch(*mock_args) for mock_args in self.mocks]
        self.maxDiff = None

    def setUp(self):
        from pyvac.config import includeme
        from .conf import settings
        super(UnauthenticatedViewTestCase, self).setUp()
        self.maxDiff = None
        # authz_policy = ACLAuthorizationPolicy()
        self.config = testing.setUp(settings=settings)
        self.config.include(includeme)
        self.session = DBSession()
        transaction.begin()

        for dummy in self.mocks:
            dummy.start()

    def tearDown(self):
        super(UnauthenticatedViewTestCase, self).tearDown()
        self.session.flush()
        transaction.commit()
        testing.tearDown()

        for dummy in reversed(self.mocks):
            dummy.stop()

    def create_request(self, params=None, environ=None, matchdict=None,
                       headers=None, path='/', cookies=None, post=None, **kw):
        if params and not isinstance(params, MultiDict):
            mparams = MultiDict()
            for k, v in params.items():
                if hasattr(v, '__iter__'):
                    [mparams.add(k, vv) for vv in v]
                else:
                    mparams.add(k, v)
                params = mparams
        rv = DummyRequest(params, environ, headers, path, cookies,
                          post, matchdict=(matchdict or {}), **kw)
        return rv

    def assertIsRedirect(self, view):
        self.assertIsInstance(view, HTTPFound)


class ViewTestCase(UnauthenticatedViewTestCase):

    def setUp(self):
        super(ViewTestCase, self).setUp()

    def set_userid(self, userid=u'admin', permissive=False):
        self.config.testing_securitypolicy(userid=userid,
                                           permissive=permissive)


class ViewAdminTestCase(ViewTestCase):

    def setUp(self):
        super(ViewAdminTestCase, self).setUp()
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
