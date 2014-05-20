# -*- coding: utf-8 -*-

import os
import sys

from pyramid.paster import get_appsettings, setup_logging

from pyvac.helpers.sqla import create_engine, dispose_engine
from pyvac.models import DBSession, Countries, VacationType


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def populate(engine):

    session = DBSession()

    cp = VacationType.by_id(session, 1)
    rtt = VacationType.by_id(session, 2)
    parent = VacationType.by_id(session, 3)

    fr_country = Countries.by_name(session, u'fr')
    session.add(fr_country)
    lu_country = Countries.by_name(session, u'lu')
    session.add(lu_country)
    us_country = Countries.by_name(session, u'us')
    session.add(us_country)
    zh_country = Countries.by_name(session, u'zh')
    session.add(zh_country)

    # CP is available for everyone
    cp.countries.append(fr_country)
    cp.countries.append(lu_country)
    cp.countries.append(us_country)
    cp.countries.append(zh_country)

    # RTT only available for france
    rtt.countries.append(fr_country)

    # parent is available for everyone
    parent.countries.append(fr_country)
    parent.countries.append(lu_country)
    parent.countries.append(us_country)
    parent.countries.append(zh_country)

    session.commit()


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)
    config_uri = argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = create_engine('pyvac', settings, scoped=False)
    populate(engine)
    dispose_engine('pyvac')
