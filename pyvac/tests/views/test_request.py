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
        view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'conflicts', u'requests', 'pyvac']))
        self.assertEqual(view[u'conflicts'], {
            1: u'Jane Doe: 10/04/2014 - 21/04/2014',
            2: u'John Doe: 10/04/2014 - 14/04/2014',
            3: u'Third Manager: 24/04/2014 - 28/04/2014'})
        self.assertEqual(len(view[u'conflicts']), 3)
        self.assertEqual(len(view[u'requests']), 3)
        self.assertIsInstance(view[u'requests'][0], Request)

    def test_get_list_manager1_ok(self):
        self.config.testing_securitypolicy(userid=u'manager1',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import List
        view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'conflicts', u'requests', 'pyvac']))
        self.assertEqual(view[u'conflicts'], {
            1: u'Jane Doe: 10/04/2014 - 21/04/2014',
            3: u'Third Manager: 24/04/2014 - 28/04/2014'})
        self.assertEqual(len(view[u'conflicts']), 2)
        self.assertEqual(len(view[u'requests']), 2)
        self.assertIsInstance(view[u'requests'][0], Request)

    def test_get_list_manager2_ok(self):
        self.config.testing_securitypolicy(userid=u'manager2',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import List
        view = List(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set([u'conflicts', u'requests', 'pyvac']))
        self.assertEqual(view[u'conflicts'], {
            2: u'John Doe: 10/04/2014 - 14/04/2014'})
        self.assertEqual(len(view[u'conflicts']), 1)
        self.assertEqual(len(view[u'requests']), 1)
        self.assertIsInstance(view[u'requests'][0], Request)

    def test_get_list_user_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import List
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
        view = Export(self.create_request())()
        self.assertEqual(set(view.keys()),
                         set(['months', 'current_month', 'pyvac']))
        self.assertEqual(len(view[u'months']), 12)

    def test_get_exported_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.views.request import Exported
        view = Exported(self.create_request({'month': 6}))()
        self.assertEqual(set(view.keys()),
                         set(['exported', 'pyvac']))
        exported = [u'#,user,from,to,number,type']
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
        view = Send(self.create_request({'date_from': '15/05/2014 - 10/05/2014'}))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)

    def test_post_send_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({'days': 4,
                                         'date_from': '05/05/2014 - 10/05/2014',
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
                                         'date_from': '05/05/2014 - 05/05/2014',
                                         'type': '1',
                                         'breakdown': 'AM',
                                         }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
