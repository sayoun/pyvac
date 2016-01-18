# -*- coding: utf-8 -*-
import json
from ldap import dn
from datetime import timedelta
from pyramid.httpexceptions import HTTPNotFound


def flash_type(message):
    if ';' in message:
        return message.split(';', 1)[0]
    return 'error'


def flash_msg(message):
    if ';' in message:
        return message.split(';', 1)[1]
    return message


def hournow(data):
    import datetime
    now = datetime.datetime.utcnow()
    return now.hour


def datenow(data):
    import datetime
    now = datetime.datetime.utcnow()
    return schedule_date(now)


def schedule_date(dt):
    return dt.strftime("%d/%m")


def is_manager(user):
    groupname = 'manager'
    for g in user.groups:
        if groupname == g.name:
            return True
    return False


def extract_cn(user_dn):
    """ Get cn from a user dn """
    try:
        for rdn in dn.str2dn(user_dn):
            rdn = rdn[0]
            if rdn[0] == 'cn':
                return rdn[1]
    except Exception:
        return user_dn


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days + 1)):
        yield start_date + timedelta(n)


def JsonHTTPNotFound(message=None):
    response = HTTPNotFound()
    response.content_type = 'application/json'
    if message:
        if isinstance(message, dict):
            msg = json.dumps(message)
        response.text = unicode(msg)
    return response


def plusify(value):
    prefix = '+' if value > 0 else ''
    return '%s%s' % (prefix, value)


def english_suffix(n):
    if 4 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, 'th')
    return '%s%s' % (n, suffix)
