import os
from pyramid.i18n import (
    TranslationStringFactory, get_localizer, make_localizer
)
from pyramid.security import authenticated_userid


def locale_negotiator(request):
    """
    Locale negotiator for pyramid views.

    This version differs from Pyramid's :py:func:`default_locale_negotiator
    <pyramid.i18n.default_locale_negotiator>` in that it gets the locale from
    the url parameter or the cookie, and fallbacks to the user's lang.
    """

    login = authenticated_userid(request)
    if login:
        from pyvac.models import DBSession, User
        session = DBSession()
        user = User.by_login(session, login)
        if user.country == 'us':
            return 'en'
        return user.country

    return None

trans = TranslationStringFactory(domain='pyvac')

localizers = {}


def add_renderer_globals(event):
    request = event['request']
    event['_'] = request.translate
    event['localizer'] = request.localizer


def add_localizer(event):
    request = event.request
    localizer = get_localizer(request)

    def auto_translate(string):
        return localizer.translate(trans(string))
    request.localizer = localizer
    request.translate = auto_translate


def translate(string, country):
    # hack to use en locale for us country
    if country == 'us':
        country = 'en'

    if country in localizers:
        localizer = localizers[country]
    else:
        here = os.path.dirname(__file__)
        local_path = os.path.join(here, '../locale')
        localizer = make_localizer(country, [local_path])
        localizers[country] = localizer

    return localizer.translate(trans(string))
