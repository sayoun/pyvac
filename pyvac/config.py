#-*- coding: utf-8 -*-

import os.path
from pyramid.interfaces import IBeforeRender
from pyramid.security import has_permission
from pyramid.url import static_path, route_path
from pyramid.exceptions import Forbidden
from pyramid_jinja2 import renderer_factory
from pyramid.settings import asbool

import yaml

try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

try:
    from logging.config import dictConfig
except ImportError:
    from logutils.dictconfig import dictConfig

from pyvac.helpers.ldap import LdapCache
from pyvac.helpers.i18n import locale_negotiator
from pyvac.helpers.holiday import init_override


def configure(filename='conf/pyvac.yaml', init_celery=True, default_app=None):
    with open(filename) as fdesc:
        conf = yaml.load(fdesc, YAMLLoader)
    if conf.get('logging'):
        dictConfig(conf.get('logging'))

    if init_celery:
        if not default_app:
            try:
                from celery import current_app as default_app
            except ImportError:  # pragma: no cover
                from celery.app import default_app

        default_app.config_from_object(conf.get('celeryconfig'))
        # XXX: must call loader for celery to register all the tasks
        default_app.loader.import_default_modules()

    return conf


def add_urlhelpers(event):
    """
    Add helpers to the template engine.
    """
    event['static_url'] = lambda x: static_path(x, event['request'])
    event['route_url'] = lambda name, *args, **kwargs: route_path(
        name, event['request'], *args, **kwargs)
    event['has_permission'] = lambda perm: has_permission(
        perm, event['request'].context, event['request'])


def includeme(config):
    """
    Pyramid includeme file for the :class:`pyramid.config.Configurator`
    """

    ldap = False
    settings = config.registry.settings
    if 'pyvac.celery.yaml' in settings:
        configure(settings['pyvac.celery.yaml'])

    if 'pyvac.use_ldap' in settings:
        ldap = asbool(settings['pyvac.use_ldap'])
        if ldap:
            LdapCache.configure(settings['pyvac.ldap.yaml'])

    # initiatlize holiday override from yaml configuration
    if 'pyvac.override_holidays_file' in settings:
        filename = settings['pyvac.override_holidays_file']
        content = None
        if os.path.isfile(filename):
            with open(filename) as fdesc:
                content = yaml.load(fdesc, YAMLLoader)
        init_override(content)

    # call includeme for models configuration
    config.include('pyvac.models')

    # call includeme for request views configuration
    config.include('pyvac.views.request')

    # call includeme for account views configuration
    config.include('pyvac.views.account')

    # call includeme for credentials views configuration
    config.include('pyvac.views.credentials')

    # Jinja configuration
    # We don't use jinja2 filename, .html instead
    config.add_renderer('.html', renderer_factory)
    # helpers
    config.add_subscriber(add_urlhelpers, IBeforeRender)
    # i18n
    config.add_translation_dirs('locale/')
    config.set_locale_negotiator(locale_negotiator)

    # Javascript + Media
    config.add_static_view('static', 'static', cache_max_age=3600)

    config.add_route('login', '/login',)
    config.add_view('pyvac.views.credentials.Login',
                    route_name='login',
                    renderer='templates/login.html')

    config.add_route('logout', '/logout')
    config.add_view('pyvac.views.credentials.Logout',
                    route_name='logout',
                    permission='user_view')

    config.add_route('sudo', '/sudo')
    config.add_view('pyvac.views.credentials.Sudo',
                    route_name='sudo',
                    permission='sudo_view',
                    renderer='templates/sudo.html')

    # Home page
    config.add_route('index', '/')
    config.add_view('pyvac.views.Index',
                    route_name='index')

    config.add_route('home', '/home')
    config.add_view('pyvac.views.Home',
                    route_name='home',
                    renderer='templates/home.html',
                    permission='user_view')

    # Forbidden
    config.add_view('pyvac.views.base.forbidden_view',
                    context=Forbidden)
    # Internal error
    config.add_view('pyvac.views.base.exception_view',
                    context=Exception)

    # Forgot password
    config.add_route('reset_password', '/reset',)
    config.add_view('pyvac.views.credentials.ResetPassword',
                    route_name='reset_password',
                    renderer='templates/password/reset.html')
    # Change password
    config.add_route('change_password', '/password/{passhash}')
    config.add_view('pyvac.views.credentials.ChangePassword',
                    route_name='change_password',
                    renderer='templates/password/change.html')

    # Request submit
    config.add_route('request_send', '/pyvac/request_send',
                     request_method='POST')
    config.add_view('pyvac.views.request.Send',
                    route_name='request_send',
                    renderer='json',
                    permission='user_view')

    # Manager view
    config.add_route('list_request', '/pyvac/request')
    config.add_view('pyvac.views.request.List',
                    route_name='list_request',
                    renderer='templates/request/list.html',
                    permission='user_view')

    config.add_route('request_accept', '/pyvac/request_accept',
                     request_method='POST')
    config.add_view('pyvac.views.request.Accept',
                    route_name='request_accept',
                    renderer='json',
                    permission='manager_view')

    config.add_route('request_refuse', '/pyvac/request_refuse',
                     request_method='POST')
    config.add_view('pyvac.views.request.Refuse',
                    route_name='request_refuse',
                    renderer='json',
                    permission='manager_view')

    config.add_route('request_cancel', '/pyvac/request_cancel',
                     request_method='POST')
    config.add_view('pyvac.views.request.Cancel',
                    route_name='request_cancel',
                    renderer='json',
                    permission='user_view')

    # Pool history
    config.add_route('pool_history', '/pyvac/pool_history/{user_id}',
                     request_method='GET')
    config.add_view('pyvac.views.request.PoolHistory',
                    route_name='pool_history',
                    renderer='templates/request/pool_history.html',
                    permission='user_view')

    config.add_route('request_history', '/pyvac/request_history/{req_id}',
                     request_method='GET')
    config.add_view('pyvac.views.request.History',
                    route_name='request_history',
                    renderer='templates/request/history.html',
                    permission='user_view')

    # Admin  view
    config.add_route('list_account', '/pyvac/account')
    config.add_view('pyvac.views.account.List',
                    route_name='list_account',
                    renderer='templates/account/list.html',
                    permission='admin_view')

    config.add_route('list_user_pool', '/pyvac/pool_users')
    config.add_view('pyvac.views.account.ListPool',
                    route_name='list_user_pool',
                    renderer='templates/account/pool.html',
                    permission='admin_view')

    config.add_route('create_account', '/pyvac/account/new')
    config.add_view('pyvac.views.account.Create',
                    route_name='create_account',
                    renderer='templates/account/create.html',
                    permission='admin_view')

    config.add_route('edit_account', '/pyvac/account/{user_id}')
    config.add_view('pyvac.views.account.Edit',
                    route_name='edit_account',
                    renderer='templates/account/edit.html',
                    permission='user_view')

    config.add_route('delete_account', '/pyvac/delete/account/{user_id}')
    config.add_view('pyvac.views.account.Delete',
                    route_name='delete_account',
                    renderer='templates/account/delete.html',
                    permission='admin_view')

    # who's who
    config.add_route('whoswho', '/who',)
    config.add_view('pyvac.views.account.Whoswho',
                    route_name='whoswho',
                    renderer='templates/whoswho.html')

    config.add_route('export_request', '/pyvac/export')
    config.add_view('pyvac.views.request.Export',
                    route_name='export_request',
                    renderer='templates/request/export.html',
                    permission='admin_view')

    config.add_route('request_export', '/pyvac/exported',
                     request_method='POST')
    config.add_view('pyvac.views.request.Exported',
                    route_name='request_export',
                    renderer='templates/request/exported.html',
                    permission='admin_view')

    config.add_route('prevision_request', '/pyvac/prevision')
    config.add_view('pyvac.views.request.Prevision',
                    route_name='prevision_request',
                    renderer='templates/request/prevision.html',
                    permission='admin_view')

    if ldap:
        config.add_route('squad_overview', '/pyvac/squad_overview')
        config.add_view('pyvac.views.request.SquadOverview',
                        route_name='squad_overview',
                        renderer='templates/request/squad_overview.html',
                        permission='manager_view')

        config.add_route('chapter_overview', '/pyvac/chapter_overview')
        config.add_view('pyvac.views.request.ChapterOverview',
                        route_name='chapter_overview',
                        renderer='templates/request/chapter_overview.html',
                        permission='manager_view')

    config.add_route('manager_overview', '/pyvac/manager_overview')
    config.add_view('pyvac.views.request.ManagerOverview',
                    route_name='manager_overview',
                    renderer='templates/request/manager_overview.html',
                    permission='manager_view')

    # Pool managment
    config.add_route('list_pools', '/pyvac/pool')
    config.add_view('pyvac.views.pool.List',
                    route_name='list_pools',
                    renderer='templates/pool/list.html',
                    permission='admin_view')

    config.add_route('create_pool', '/pyvac/pool/new')
    config.add_view('pyvac.views.pool.Create',
                    route_name='create_pool',
                    renderer='templates/pool/create.html',
                    permission='admin_view')

    config.add_route('edit_pool', '/pyvac/pool/{pool_id}')
    config.add_view('pyvac.views.pool.Edit',
                    route_name='edit_pool',
                    renderer='templates/pool/edit.html',
                    permission='user_view')

    config.add_route('delete_pool', '/pyvac/delete/pool/{pool_id}')
    config.add_view('pyvac.views.pool.Delete',
                    route_name='delete_pool',
                    renderer='templates/pool/delete.html',
                    permission='admin_view')

    # Holiday request
    config.add_route('list_holiday', '/pyvac/list_holiday',
                     request_method='POST')
    config.add_view('pyvac.views.holiday.List',
                    route_name='list_holiday',
                    renderer='json',
                    permission='user_view')

    # Retrieve today vacations
    config.add_route('request_off', '/pyvac/off',
                     request_method='GET')
    config.add_view('pyvac.views.request.Off',
                    route_name='request_off',
                    renderer='json')

    # Retrieve today vacations (HTML)
    config.add_route('request_off_html', '/pyvac/off.html')
    config.add_view('pyvac.views.base.ViewBase',
                    route_name='request_off_html',
                    renderer='templates/off.html')
