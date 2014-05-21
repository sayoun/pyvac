from pyramid.i18n import TranslationStringFactory, get_localizer
from pyramid.security import authenticated_userid
from pyvac.models import DBSession, User


def locale_negotiator(request):
    """
    Locale negotiator for pyramid views.

    This version differs from Pyramid's :py:func:`default_locale_negotiator
    <pyramid.i18n.default_locale_negotiator>` in that it gets the locale from
    the url parameter or the cookie, and fallbacks to the user's lang.
    """

    login = authenticated_userid(request)
    if login:
        session = DBSession()
        user = User.by_login(session, login)
        if user.country == 'us':
            return 'en'
        return user.country

    return None

trans = TranslationStringFactory(domain='pyvac')


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
