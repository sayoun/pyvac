# -*- coding: utf-8 -*-
from pyramid.config import Configurator
from pyramid.authorization import ACLAuthorizationPolicy as ACLPolicy
from pyramid.session import UnencryptedCookieSessionFactoryConfig

from .security import groupfinder, RootFactory

from .config import includeme  # used by pyramid
from .models import create_engine
from .helpers.i18n import locale_negotiator
from .helpers.authentication import RouteSwithchAuthPolicy

__version__ = '0.1'


def main(global_config, **settings):
    settings = dict(settings)

    # Scoping sessions for Pyramid ensure session are commit/rollback
    # after the template has been rendered
    create_engine(settings, scoped=True)

    session_factory = UnencryptedCookieSessionFactoryConfig(
        settings['pyvac.cookie_key']
    )

    authn_policy = RouteSwithchAuthPolicy(secret=settings['pyvac.cookie_key'],
                                          callback=groupfinder)
    authz_policy = ACLPolicy()

    config = Configurator(settings=settings,
                          root_factory=RootFactory,
                          locale_negotiator=locale_negotiator,
                          authentication_policy=authn_policy,
                          authorization_policy=authz_policy,
                          session_factory=session_factory)
    config.end()

    return config.make_wsgi_app()
