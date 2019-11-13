#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import os
import sys
import yaml
try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader

import caldav
from pyramid.paster import get_appsettings
import transaction

from pyvac.models import create_engine, DBSession, Request
from pyvac.helpers.calendar import addToCal
from pyvac.helpers.ical import parse_event
# XXX: if needed to delete entries
# from pyvac.helpers.calendar import delFromCal


def get_calendar(caldav_url):
    """
    Get the calendar using credentials from `credentials.py`.
    """
    url = caldav_url
    client = caldav.DAVClient(url)
    princ = caldav.Principal(client, url)
    return princ.calendars()[0]


def replay(settings):

    with open(settings['pyvac.celery.yaml']) as fdesc:
        Conf = yaml.load(fdesc, YAMLLoader)
    caldav_url = Conf.get('caldav').get('url')

    # XXX Register the database
    create_engine(settings, scoped=True)
    session = DBSession()

    calendar = get_calendar(caldav_url)
    requests = Request.find(session,
                            where=(Request.status == 'APPROVED_ADMIN',),
                            order_by=Request.user_id)
    print(('total requests', len(requests)))
    print()

    req_to_add = []

    # for each requests
    for req in requests:
        print(('-' * 10))
        print((req.id, req.summarycal, req.date_from, req.date_to))
        # check if entry in caldav exists
        results = calendar.date_search(req.date_from, req.date_to)
        if not results:
            # need to add missing entry in caldav
            print('need to insert request')
            req_to_add.append(req.id)
        else:
            summaries = []
            for event in results:
                try:
                    parse_event(event)
                except Exception:
                    continue
                event.load()
                # XXX: if needed to delete entries
                # uid = event.instance.vevent.uid.value
                # ics = '%s/%s.ics' % (caldav_url, uid)
                # print delFromCal(caldav_url, ics)
                summary = event.instance.vevent.summary.value
                summaries.append(summary)
            if req.summarycal not in summaries:
                print('need to insert request')
                req_to_add.append(req.id)

    for req_id in set(req_to_add):
        req = Request.by_id(session, req_id)
        print(('processing', req.id, req.summarycal, req.date_from, req.date_to))
        ics_url = addToCal(caldav_url,
                           req.date_from,
                           req.date_to,
                           req.summarycal)
        # save ics url in request
        req.ics_url = ics_url
        session.add(req)

    session.flush()
    transaction.commit()


def usage(argv):
    cmd = os.path.basename(argv[0])
    print(('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd)))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)

    config_uri = argv[1]
    settings = get_appsettings(config_uri)

    replay(settings)


if __name__ == '__main__':
    main()
