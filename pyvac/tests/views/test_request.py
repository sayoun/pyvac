from freezegun import freeze_time

from pyvac.tests import case
from pyvac.tests.mocks.tasks import DummyTasks
from pyvac.tests.mocks.celery import subtask


class RequestTestCase(case.ViewTestCase):

    mocks = [
        ('celery.registry.tasks', DummyTasks()),
        ('celery.task.subtask', subtask),
    ]

    def setUp(self):
        super(RequestTestCase, self).setUp()

    def tearDown(self):
        super(RequestTestCase, self).tearDown()

    def test_get_list_admin_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import List
        with freeze_time('2015-03-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'conflicts', u'requests', 'pyvac']))
        self.assertEqual(view[u'conflicts'], {
            1: u'Jane Doe: 10/04/2015 - 21/04/2015',
            2: u'John Doe: 10/04/2015 - 14/04/2015',
            3: u'Third Manager: 24/04/2015 - 28/04/2015'})

        self.assertEqual(len(view[u'conflicts']), 3)
        self.assertEqual(len(view[u'requests']), 7)
        self.assertIsInstance(view[u'requests'][0], Request)

    def test_get_list_manager1_ok(self):
        self.config.testing_securitypolicy(userid=u'manager1',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import List
        with freeze_time('2015-03-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'conflicts', u'requests', 'pyvac']))
        self.assertEqual(view[u'conflicts'], {
            1: u'Jane Doe: 10/04/2015 - 21/04/2015',
            3: u'Third Manager: 24/04/2015 - 28/04/2015'})
        self.assertEqual(len(view[u'conflicts']), 2)
        self.assertEqual(len(view[u'requests']), 6)
        self.assertIsInstance(view[u'requests'][0], Request)

    def test_get_list_manager2_ok(self):
        self.config.testing_securitypolicy(userid=u'manager2',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import List
        with freeze_time('2015-03-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'conflicts', u'requests', 'pyvac']))
        self.assertEqual(view[u'conflicts'], {
            2: u'John Doe: 10/04/2015 - 14/04/2015'})
        self.assertEqual(len(view[u'conflicts']), 1)
        self.assertEqual(len(view[u'requests']), 1)
        self.assertIsInstance(view[u'requests'][0], Request)

    def test_get_list_user_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import List
        with freeze_time('2015-03-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'conflicts', u'requests', 'pyvac']))
        self.assertEqual(len(view[u'requests']), 1)
        self.assertIsInstance(view[u'requests'][0], Request)

    def test_set_status_accept_admin_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Accept
        req_id = 1
        req = Request.by_id(self.session, req_id)
        orig_status = req.status
        status = Accept(self.create_request({'request_id': req_id}))()
        self.assertEqual(status, u'APPROVED_ADMIN')
        self.session.commit()
        self.assertEqual(req.status, u'APPROVED_ADMIN')
        self.assertEqual(req.notified, False)
        req.update_status(orig_status)

    def test_set_status_accept_manager_ok(self):
        self.config.testing_securitypolicy(userid=u'manager1',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Accept
        req_id = 1
        req = Request.by_id(self.session, req_id)
        orig_status = req.status
        status = Accept(self.create_request({'request_id': req_id}))()
        self.assertEqual(status, u'ACCEPTED_MANAGER')
        self.session.commit()
        self.assertEqual(req.status, u'ACCEPTED_MANAGER')
        self.assertEqual(req.notified, False)
        req.update_status(orig_status)

    def test_set_status_refuse_admin_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Refuse
        req_id = 1
        req = Request.by_id(self.session, req_id)
        orig_status = req.status
        status = Refuse(self.create_request({'request_id': req_id}))()
        self.assertEqual(status, u'DENIED')
        self.session.commit()
        self.assertEqual(req.status, u'DENIED')
        self.assertEqual(req.notified, False)
        req.update_status(orig_status)

    def test_set_status_refuse_admin_reason_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Refuse
        req_id = 1
        req = Request.by_id(self.session, req_id)
        orig_status = req.status
        status = Refuse(self.create_request({'request_id': req_id,
                                             'reason': u'we need you'}))()
        self.assertEqual(status, u'DENIED')
        self.session.commit()
        self.assertEqual(req.status, u'DENIED')
        self.assertEqual(req.notified, False)
        self.assertEqual(req.reason, u'we need you')
        req.update_status(orig_status)

    def test_set_status_refuse_manager_ok(self):
        self.config.testing_securitypolicy(userid=u'manager1',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Refuse
        req_id = 1
        req = Request.by_id(self.session, req_id)
        orig_status = req.status
        status = Refuse(self.create_request({'request_id': req_id}))()
        self.assertEqual(status, u'DENIED')
        self.session.commit()
        self.assertEqual(req.status, u'DENIED')
        self.assertEqual(req.notified, False)
        req.update_status(orig_status)

    def test_set_status_cancel_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Cancel
        req_id = 1
        req = Request.by_id(self.session, req_id)
        orig_status = req.status
        with freeze_time('2015-03-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            status = Cancel(self.create_request({'request_id': req_id}))()
            self.assertEqual(status, u'CANCELED')
            self.session.commit()
            self.assertEqual(req.status, u'CANCELED')
            self.assertEqual(req.notified, False)
            req.update_status(orig_status)

    def test_set_status_cancel_ko_consumed_after(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Cancel
        req_id = 6
        req = Request.by_id(self.session, req_id)
        self.assertEqual(req.status, u'APPROVED_ADMIN')
        with freeze_time('2099-02-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            status = Cancel(self.create_request({'request_id': req_id}))()
            self.assertEqual(status, u'APPROVED_ADMIN')

    def test_set_status_cancel_ko_consumed_during(self):
        self.config.testing_securitypolicy(userid=u'manager3',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Cancel
        req_id = 5
        req = Request.by_id(self.session, req_id)
        self.assertEqual(req.status, u'APPROVED_ADMIN')
        with freeze_time('2015-04-25',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            status = Cancel(self.create_request({'request_id': req_id}))()
            self.assertEqual(status, u'APPROVED_ADMIN')

    def test_set_status_cancel_consumed_admin_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Cancel
        req_id = 6
        req = Request.by_id(self.session, req_id)
        self.assertEqual(req.status, u'APPROVED_ADMIN')
        orig_status = req.status
        with freeze_time('2099-02-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            status = Cancel(self.create_request({'request_id': req_id}))()
            self.assertEqual(status, u'CANCELED')
            self.session.commit()
            self.assertEqual(req.status, u'CANCELED')
            self.assertEqual(req.notified, False)
            req.update_status(orig_status)

    def test_get_export_choice_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.views.request import Export
        with freeze_time('2015-02-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            view = Export(self.create_request())()
            self.assertEqual(set(view.keys()),
                             set(['months', 'current_month', 'pyvac']))
            self.assertEqual(len(view[u'months']), 24)

    def test_get_exported_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.views.request import Exported
        view = Exported(self.create_request({'month': '6/2014'}))()
        self.assertEqual(set(view.keys()),
                         set(['exported', 'pyvac']))
        exported = [u'#,lastname,firstname,from,to,number,type']
        self.assertEqual(view[u'exported'].split('\n'), exported)

    def test_post_send_no_param_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request())()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)

    def test_post_send_wrong_date_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'date_from': 'foo'}))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)

    def test_post_send_wrong_period_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'date_from': '15/05/2015 - 10/05/2015'}))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)

    def test_post_send_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'days': 4,
                                         'date_from': '05/05/2015 - 10/05/2015',
                                         'type': '1',
                                         'breakdown': 'FULL',
                                         }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)

    def test_post_send_half_day_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'days': 0.5,
                                         'date_from': '05/05/2015 - 05/05/2015',
                                         'type': '1',
                                         'breakdown': 'AM',
                                         }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)

    def test_post_send_sudo_default_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'days': 4,
                                         'date_from': '05/05/2015 - 10/05/2015',
                                         'type': '1',
                                         'breakdown': 'FULL',
                                         'sudo_user': '-1',
                                         }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        admin_user = User.by_login(self.session, u'admin')
        self.assertEqual(last_req.user_id, admin_user.id)
        self.assertEqual(last_req.status, u'PENDING')
        self.assertFalse(last_req.notified)

    def test_post_send_sudo_other_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'days': 4,
                                         'date_from': '05/05/2015 - 10/05/2015',
                                         'type': '1',
                                         'breakdown': 'FULL',
                                         'sudo_user': '2',
                                         }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        target_user = User.by_login(self.session, u'manager1')
        self.assertEqual(last_req.user_id, target_user.id)
        self.assertEqual(last_req.status, u'APPROVED_ADMIN')
        self.assertTrue(last_req.notified)

    def test_post_send_sudo_unknown_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'days': 4,
                                         'date_from': '05/05/2015 - 10/05/2015',
                                         'type': '1',
                                         'breakdown': 'FULL',
                                         'sudo_user': '200',
                                         }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        admin_user = User.by_login(self.session, u'admin')
        self.assertEqual(last_req.user_id, admin_user.id)
        self.assertEqual(last_req.status, u'PENDING')
        self.assertFalse(last_req.notified)

    def test_post_send_rtt_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2016-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({'days': 1,
                                           'date_from': '05/05/2015 - 05/05/2015',
                                           'type': '2',
                                           'breakdown': 'AM',
                                           })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)

    def test_post_send_rtt_usage_empty_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        def mock_get_rtt_usage(self, session):
            """ Get rrt usage for a user """
            return

        orig_get_rtt_usage = User.get_rtt_usage
        User.get_rtt_usage = mock_get_rtt_usage
        user = User.by_login(self.session, u'janedoe')
        rtt_data = user.get_rtt_usage(self.session)
        self.assertIsNone(rtt_data)

        view = Send(self.create_request({'days': 1,
                                         'date_from': '05/05/2015 - 05/05/2015',
                                         'type': '2',
                                         'breakdown': 'AM',
                                         }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        User.get_rtt_usage = orig_get_rtt_usage

    def test_post_send_rtt_usage_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        def mock_get_rtt_usage(self, session):
            """ Get rrt usage for a user """
            return {'allowed': 10, 'left': 0, 'state': 'error',
                    'taken': 10.0, 'year': 2014}

        orig_get_rtt_usage = User.get_rtt_usage
        User.get_rtt_usage = mock_get_rtt_usage
        user = User.by_login(self.session, u'janedoe')
        rtt_data = user.get_rtt_usage(self.session)
        self.assertTrue(rtt_data)

        request = self.create_request({'days': 1,
                                       'date_from': '05/05/2015 - 05/05/2015',
                                       'type': '2',
                                       'breakdown': 'AM',
                                       })
        view = Send(request)()
        self.assertIsRedirect(view)
        # no new requests were made
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = ['error;No RTT left to take.']
        self.assertEqual(request.session.pop_flash(), expected)
        User.get_rtt_usage = orig_get_rtt_usage

    def test_post_send_rtt_usage_not_enough_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        def mock_get_rtt_usage(self, session):
            """ Get rrt usage for a user """
            return {'allowed': 10, 'left': 0.5, 'state': 'error',
                    'taken': 9.5, 'year': 2014}

        orig_get_rtt_usage = User.get_rtt_usage
        User.get_rtt_usage = mock_get_rtt_usage
        user = User.by_login(self.session, u'janedoe')
        rtt_data = user.get_rtt_usage(self.session)
        self.assertTrue(rtt_data)

        request = self.create_request({'days': 1,
                                       'date_from': '05/05/2015 - 05/05/2015',
                                       'type': '2',
                                       'breakdown': 'FULL',
                                       })
        view = Send(request)()
        self.assertIsRedirect(view)
        # no new requests were made
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = ['error;You only have 0.5 RTT to use.']
        self.assertEqual(request.session.pop_flash(), expected)
        User.get_rtt_usage = orig_get_rtt_usage
