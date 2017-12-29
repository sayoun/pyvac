# -*- coding: utf-8 -*-
from datetime import datetime
from freezegun import freeze_time

from pyvac.tests import case
from pyvac.tests.mocks.tasks import DummyTasks
from pyvac.tests.mocks.celery import subtask

from mock import patch, MagicMock, PropertyMock
from dateutil.relativedelta import relativedelta


def mock_pool(amount, date_start, date_end):
    mocked_pool = MagicMock()
    type(mocked_pool).amount = PropertyMock(return_value=amount)
    type(mocked_pool).date_start = PropertyMock(return_value=date_start) # noqa
    type(mocked_pool).date_end = PropertyMock(return_value=date_end) # noqa
    return mocked_pool


class RequestTestCase(case.ViewTestCase):

    mocks = [
        ('celery.registry.tasks', DummyTasks()),
        ('celery.task.subtask', subtask),
    ]

    def setUp(self):
        super(RequestTestCase, self).setUp()

    def tearDown(self):
        super(RequestTestCase, self).tearDown()

    def delete_last_req(self, request):
        for entry in request.history:
            self.session.delete(entry)
        self.session.delete(request)

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
                         set([u'conflicts', u'requests', u'pyvac',
                              u'next', u'past']))
        self.assertEqual(view[u'conflicts'], {
            1: {u'': u'Jane Doe: 10/04/2015 - 21/04/2015'},
            2: {u'': u'John Doe: 10/04/2015 - 14/04/2015'},
            3: {u'': u'Third Manager: 24/04/2015 - 28/04/2015'},
            12: {'': u'John Doe: 10/04/2015 - 14/04/2015\n'
                     u'Jane Doe: 10/04/2015 - 21/04/2015'}})
        self.assertEqual(len(view[u'conflicts']), 4)
        self.assertEqual(len(view[u'requests']), 10)
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
                         set([u'conflicts', u'requests', u'pyvac',
                              u'next', u'past']))
        self.assertEqual(view[u'conflicts'], {
            1: {u'': u'Jane Doe: 10/04/2015 - 21/04/2015'},
            3: {u'': u'Third Manager: 24/04/2015 - 28/04/2015'},
            12: {'': u'John Doe: 10/04/2015 - 14/04/2015\n'
                     u'Jane Doe: 10/04/2015 - 21/04/2015'}})
        self.assertEqual(len(view[u'conflicts']), 3)
        self.assertEqual(len(view[u'requests']), 8)
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
                         set([u'conflicts', u'requests', u'pyvac',
                              u'next', u'past']))
        self.assertEqual(view[u'conflicts'], {
            2: {u'': u'John Doe: 10/04/2015 - 14/04/2015'}})
        self.assertEqual(len(view[u'conflicts']), 1)
        self.assertEqual(len(view[u'requests']), 2)
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
                         set([u'conflicts', u'requests', u'pyvac',
                              u'next', u'past']))
        self.assertEqual(len(view[u'requests']), 2)
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
        exported = [u'#,registration_number,lastname,firstname,from,to,number,type,label,message'] # noqa
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
        view = Send(self.create_request({
            'date_from': '15/05/2015 - 10/05/2015'}))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)

    def test_post_send_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({
            'days': 4,
            'date_from': '05/05/2015 - 10/05/2015',
            'type': '1',
            'breakdown': 'FULL',
        }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)

    def test_post_send_n_1_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request, User, CPVacation
        from pyvac.views.request import Send

        total_req = Request.find(self.session, count=True)

        jdoe = User.by_login(self.session, u'jdoe')
        with freeze_time('2016-12-23',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):

            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime.now() - relativedelta(months=5) # noqa
                CPVacation.users_base = {'jdoe': {'n_1': 20, 'restants': 25}}
                CPVacation.epoch = datetime(2016, 6, 1)
                pool = jdoe.get_cp_usage(self.session)
                self.assertEqual(pool['n_1']['left'], 20)

                request = self.create_request({
                    'days': 5,
                    'date_from': '09/01/2017 - 13/01/2017',
                    'type': '1',
                    'breakdown': 'FULL',
                    'sudo_user': '5',
                })
                view = Send(request)()
                self.session.commit()

                self.assertIsRedirect(view)
                self.assertEqual(Request.find(self.session, count=True), total_req + 1)  # noqa
                last_req = Request.find(self.session)[-1]
                self.assertEqual(last_req.user_id, jdoe.id)
                self.assertEqual(last_req.status, u'APPROVED_ADMIN')
                self.assertEqual(last_req.days, 5.0)
                pool = jdoe.get_cp_usage(self.session)
                self.assertEqual(pool['n_1']['left'], 15)
                self.delete_last_req(last_req)
                self.session.flush()
                self.session.commit()

        with freeze_time('2017-01-02',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):

            with patch('pyvac.models.User.arrival_date',
                       new_callable=PropertyMock) as mock_foo:
                mock_foo.return_value = datetime.now() - relativedelta(months=5) # noqa
                CPVacation.users_base = {'jdoe': {'n_1': 20, 'restants': 25}}
                CPVacation.epoch = datetime(2016, 6, 1)
                pool = jdoe.get_cp_usage(self.session)
                self.assertEqual(pool['n_1']['left'], 0)
                self.assertEqual(pool['restant']['left'], 25)

                request = self.create_request({
                    'days': 5,
                    'date_from': '16/01/2017 - 20/01/2017',
                    'type': '1',
                    'breakdown': 'FULL',
                    'sudo_user': '5',
                })
                view = Send(request)()
                self.session.commit()

                self.assertIsRedirect(view)
                self.assertEqual(Request.find(self.session, count=True), total_req + 1)  # noqa
                last_req = Request.find(self.session)[-1]
                self.assertEqual(last_req.user_id, jdoe.id)
                self.assertEqual(last_req.status, u'APPROVED_ADMIN')
                self.assertEqual(last_req.days, 5.0)
                pool = jdoe.get_cp_usage(self.session)
                self.assertEqual(pool['n_1']['left'], 0)
                self.assertEqual(pool['restant']['left'], 20.0)
                self.delete_last_req(last_req)

    def test_post_send_half_day_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({
            'days': 0.5,
            'date_from': '05/05/2015 - 05/05/2015',
            'type': '1',
            'breakdown': 'AM',
        }))()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)

    def test_post_send_half_day_ko(self):
        self.config.testing_securitypolicy(userid=u'jdoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2011-07-14',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 0.5,
                'date_from': '24/08/2011 - 24/08/2011',
                'type': '1',
                'breakdown': 'AM',
            })
            view = Send(request)()
        self.assertIsRedirect(view)
        expected = ['error;Invalid period: days already requested.']
        self.assertEqual(request.session.pop_flash(), expected)
        self.assertEqual(Request.find(self.session, count=True), total_req)

    def test_post_send_half_day_other_half_ok(self):
        self.config.testing_securitypolicy(userid=u'jdoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2011-07-14',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 0.5,
                'date_from': '24/08/2011 - 24/08/2011',
                'type': '1',
                'breakdown': 'PM',
            })
            view = Send(request)()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)

    def test_post_send_sudo_default_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({
            'days': 4,
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
        self.delete_last_req(last_req)

    def test_post_send_sudo_other_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({
            'days': 4,
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
        self.delete_last_req(last_req)

    def test_post_send_sudo_unknown_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)
        view = Send(self.create_request({
            'days': 4,
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
        self.delete_last_req(last_req)

    def test_post_send_rtt_holiday_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send

        total_req = Request.find(self.session, count=True)

        janedoe = User.by_login(self.session, u'janedoe')
        old_created_at = janedoe.created_at
        janedoe.created_at = janedoe.created_at.replace(month=1)
        janedoe.get_rtt_usage(self.session)

        with freeze_time('2016-12-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 5,
                'date_from': '11/07/2016 - 15/07/2016',
                'type': '2',
                'breakdown': 'FULL',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        self.assertEqual(last_req.status, u'PENDING')
        self.assertEqual(last_req.days, 4.0)
        janedoe.created_at = old_created_at
        self.delete_last_req(last_req)

    def test_post_send_holiday_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '11/11/2015 - 11/11/2015',
                'type': '1',
                'breakdown': 'FULL',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = ['error;Invalid value for days.']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_exception_reason_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '12/11/2015 - 12/11/2015',
                'type': '6',
                'breakdown': 'FULL',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = [u'error;You must provide a reason for '
                    'Exceptionnel requests']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_exception_reason_strip_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '12/11/2015 - 12/11/2015',
                'type': '6',
                'breakdown': 'FULL',
                'exception_text': '             ',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = [u'error;You must provide a reason for '
                    'Exceptionnel requests']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_exception_reason_length_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '12/11/2015 - 12/11/2015',
                'type': '6',
                'breakdown': 'FULL',
                'exception_text': "I need to see Star Wars, I'm a huge fan"
                                  "please, please, please, please, please, "
                                  "please, please, please, please, please, "
                                  "please, please, please, please, please, "
                                  "please, please, please, please, please, "
                                  "please, please, please, please, please, "
                                  "please, please, please, please, please, ",
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = [u'error;Exceptionnel reason must not exceed 140 '
                    'characters']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_exception_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '12/11/2015 - 12/11/2015',
                'type': '6',
                'breakdown': 'FULL',
                'exception_text': "I need to see Star Wars, because "
                                  "I'm a really huge fan !!!",
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        self.assertEqual(last_req.type, u'Exceptionnel')
        self.delete_last_req(last_req)

    def test_post_send_recovery_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        msg = u"I need to see Star Wars, because I'm a really huge fan !!!"
        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '12/11/2015 - 12/11/2015',
                'type': '4',
                'breakdown': 'FULL',
                'exception_text': msg,
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        self.assertEqual(last_req.type, u'Récupération')
        self.assertEqual(last_req.message, msg)
        self.delete_last_req(last_req)

    def test_post_send_recovery_no_message_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '12/11/2015 - 12/11/2015',
                'type': '4',
                'breakdown': 'FULL',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        self.assertEqual(last_req.type, u'Récupération')
        self.assertEqual(last_req.message, None)
        self.delete_last_req(last_req)

    def test_post_send_overlap_ko(self):
        self.config.testing_securitypolicy(userid=u'manager3',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-04-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 8,
                'date_from': '22/04/2015 - 30/04/2015',
                'type': '1',
                'breakdown': 'FULL',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = ['error;Invalid period: days already requested.']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_rtt_ok(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with freeze_time('2015-10-01',
                         ignore=['celery', 'psycopg2', 'sqlalchemy',
                                 'icalendar']):
            request = self.create_request({
                'days': 1,
                'date_from': '05/05/2015 - 05/05/2015',
                'type': '2',
                'breakdown': 'AM',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)

    def test_post_send_rtt_year_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with patch('pyvac.models.User.pool',
                   new_callable=PropertyMock) as mock_foo:
            mocked_pool = mock_pool(10, datetime(2015, 1, 1),
                                    datetime(2015, 12, 31))
            mock_foo.return_value = {'RTT': mocked_pool}

            user = User.by_login(self.session, u'janedoe')
            rtt_pool = user.pool.get('RTT')
            self.assertTrue(rtt_pool)

            request = self.create_request({
                'days': 1,
                'date_from': '06/05/2016 - 06/05/2016',
                'type': '2',
                'breakdown': 'AM',
            })
            view = Send(request)()

        self.assertIsRedirect(view)
        # no new requests were made
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = ['error;RTT can only be used between 01/01/2015 and 31/12/2015']  # noqa
        self.assertEqual(request.session.pop_flash(), expected)

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

        view = Send(self.create_request({
            'days': 1,
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

        with patch('pyvac.models.User.pool',
                   new_callable=PropertyMock) as mock_foo:
            mocked_pool = mock_pool(0, datetime(2014, 1, 1),
                                    datetime(2014, 12, 31))
            mock_foo.return_value = {'RTT': mocked_pool}

            user = User.by_login(self.session, u'janedoe')
            rtt_pool = user.pool.get('RTT')
            self.assertTrue(rtt_pool)

            request = self.create_request({'days': 1,
                                           'date_from': '05/05/2015 - 05/05/2015', # noqa
                                           'type': '2',
                                           'breakdown': 'AM',
                                           })
            view = Send(request)()

        self.assertIsRedirect(view)
        # no new requests were made
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = ['error;No RTT left to take.']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_vacation_type_visibility_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        request = self.create_request({'days': 1,
                                       'date_from': '05/05/2015 - 05/05/2015',
                                       'type': '5',
                                       'breakdown': 'FULL',
                                       })
        view = Send(request)()
        self.assertIsRedirect(view)
        # no new requests were made
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = [u'error;You are not allowed to use type: Maladie']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_vacation_type_visibility_ok(self):
        self.config.testing_securitypolicy(userid=u'admin',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        request = self.create_request({'days': 1,
                                       'date_from': '05/05/2015 - 05/05/2015',
                                       'type': '5',
                                       'breakdown': 'FULL',
                                       'sudo_user': -1,
                                       })
        view = Send(request)()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        self.assertEqual(last_req.type, u'Maladie')
        self.delete_last_req(last_req)

    def test_post_send_rtt_usage_not_enough_ko(self):
        self.config.testing_securitypolicy(userid=u'janedoe',
                                           permissive=True)
        from pyvac.models import Request, User
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with patch('pyvac.models.User.pool',
                   new_callable=PropertyMock) as mock_foo:
            mocked_pool = mock_pool(0.5, datetime(2014, 1, 1),
                                    datetime(2014, 12, 31))
            mock_foo.return_value = {'RTT': mocked_pool}

            user = User.by_login(self.session, u'janedoe')
            rtt_pool = user.pool.get('RTT')
            self.assertTrue(rtt_pool)

            request = self.create_request({'days': 1,
                                           'date_from': '05/05/2015 - 05/05/2015', # noqa
                                           'type': '2',
                                           'breakdown': 'FULL',
                                           })
            view = Send(request)()

        self.assertIsRedirect(view)
        # no new requests were made
        self.assertEqual(Request.find(self.session, count=True), total_req)
        expected = ['error;You only have 0.5 RTT to use.']
        self.assertEqual(request.session.pop_flash(), expected)

    def test_post_send_cp_lu_full_ok(self):
        self.config.testing_securitypolicy(userid=u'sarah.doe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=5) # noqa
            request = self.create_request({
                'days': 4,
                'date_from': '05/10/2016 - 10/10/2016',
                'type': '1',
                'breakdown': 'FULL',
            })
            view = Send(request)()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        self.assertEqual(last_req.days, 32.0)

    def test_post_send_cp_lu_half_ok(self):
        self.config.testing_securitypolicy(userid=u'sarah.doe',
                                           permissive=True)
        from pyvac.models import Request
        from pyvac.views.request import Send
        total_req = Request.find(self.session, count=True)

        with patch('pyvac.models.User.arrival_date',
                   new_callable=PropertyMock) as mock_foo:
            mock_foo.return_value = datetime.now() - relativedelta(months=5) # noqa
            request = self.create_request({
                'days': 0.5,
                'date_from': '17/10/2016 - 17/10/2016',
                'type': '1',
                'breakdown': 'AM',
            })
            view = Send(request)()
        self.assertIsRedirect(view)
        self.assertEqual(Request.find(self.session, count=True), total_req + 1)
        last_req = Request.find(self.session)[-1]
        self.assertEqual(last_req.days, 4.0)
