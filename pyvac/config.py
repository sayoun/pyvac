#-*- coding: utf-8 -*-

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
    event['has_permission'] = lambda perm: has_permission(perm,
                                                          event['request'].context,
                                                          event['request'])


def includeme(config):
    """
    Pyramid includeme file for the :class:`pyramid.config.Configurator`
    """

    settings = config.registry.settings
    if 'pyvac.celery.yaml' in settings:
        configure(settings['pyvac.celery.yaml'])

    if 'pyvac.use_ldap' in settings:
        ldap = asbool(settings['pyvac.use_ldap'])
        if ldap:
            LdapCache.configure(settings['pyvac.ldap.yaml'])

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

    config.add_route(u'login', u'/login',)
    config.add_view(u'pyvac.views.credentials.Login',
                    route_name=u'login',
                    renderer=u'templates/login.html')

    config.add_route(u'logout', u'/logout')
    config.add_view(u'pyvac.views.credentials.Logout',
                    route_name=u'logout',
                    permission=u'user_view')

    config.add_route('sudo', '/sudo')
    config.add_view(u'pyvac.views.credentials.Sudo',
                    route_name=u'sudo',
                    permission=u'user_view',
                    renderer='templates/sudo.html')

    # Home page
    config.add_route(u'index', u'/')
    config.add_view(u'pyvac.views.Index',
                    route_name=u'index')

    config.add_route('home', '/home')
    config.add_view(u'pyvac.views.Home',
                    route_name=u'home',
                    permission=u'user_view',
                    renderer='templates/home.html')

    # Forbidden
    config.add_view(u'pyvac.views.base.forbidden_view',
                    context=Forbidden)
    # Internal error
    config.add_view(u'pyvac.views.base.exception_view',
                    context=Exception)

    # Forgot password
    config.add_route(u'reset_password', u'/reset',)
    config.add_view(u'pyvac.views.credentials.ResetPassword',
                    route_name=u'reset_password',
                    renderer=u'templates/password/reset.html')
    # Change password
    config.add_route(u'change_password', u'/password/{passhash}')
    config.add_view(u'pyvac.views.credentials.ChangePassword',
                    route_name=u'change_password',
                    renderer=u'templates/password/change.html')

    # Request submit
    config.add_route('request_send', u'/pyvac/request_send',
                     request_method=u'POST')
    config.add_view(u'pyvac.views.request.Send',
                    route_name=u'request_send',
                    renderer='json')

    # Manager view
    config.add_route(u'list_request', u'/pyvac/request')
    config.add_view(u'pyvac.views.request.List',
                    route_name=u'list_request',
                    renderer=u'templates/request/list.html',
                    permission=u'user_view')

    config.add_route('request_accept', u'/pyvac/request_accept',
                     request_method=u'POST')
    config.add_view(u'pyvac.views.request.Accept',
                    route_name=u'request_accept',
                    renderer='json',
                    permission=u'manager_view')

    config.add_route('request_refuse', u'/pyvac/request_refuse',
                     request_method=u'POST')
    config.add_view(u'pyvac.views.request.Refuse',
                    route_name=u'request_refuse',
                    renderer='json',
                    permission=u'manager_view')

    config.add_route('request_cancel', u'/pyvac/request_cancel',
                     request_method=u'POST')
    config.add_view(u'pyvac.views.request.Cancel',
                    route_name=u'request_cancel',
                    renderer='json',
                    permission=u'user_view')

    # Admin  view
    config.add_route(u'list_account', u'/pyvac/account')
    config.add_view(u'pyvac.views.account.List',
                    route_name=u'list_account',
                    renderer=u'templates/account/list.html',
                    permission=u'admin_view')

    config.add_route(u'create_account', u'/pyvac/account/new')
    config.add_view(u'pyvac.views.account.Create',
                    route_name=u'create_account',
                    renderer=u'templates/account/create.html',
                    permission=u'admin_view')

    config.add_route(u'edit_account', u'/pyvac/account/{user_id}')
    config.add_view(u'pyvac.views.account.Edit',
                    route_name=u'edit_account',
                    renderer=u'templates/account/edit.html',
                    permission=u'user_view')

    config.add_route(u'delete_account', u'/pyvac/delete/account/{user_id}')
    config.add_view(u'pyvac.views.account.Delete',
                    route_name=u'delete_account',
                    renderer=u'templates/account/delete.html',
                    permission=u'admin_view')

    config.add_route(u'export_request', u'/pyvac/export')
    config.add_view(u'pyvac.views.request.Export',
                    route_name=u'export_request',
                    renderer=u'templates/request/export.html',
                    permission=u'admin_view')

    config.add_route(u'request_export', u'/pyvac/exported',
                     request_method=u'POST')
    config.add_view(u'pyvac.views.request.Exported',
                    route_name=u'request_export',
                    renderer=u'templates/request/exported.html',
                    permission=u'admin_view')

    config.add_route(u'prevision_request', u'/pyvac/prevision')
    config.add_view(u'pyvac.views.request.Prevision',
                    route_name=u'prevision_request',
                    renderer=u'templates/request/prevision.html',
                    permission=u'admin_view')
