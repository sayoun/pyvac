# -*- coding: utf-8 -*-

import os
import sys

from pyramid.paster import get_appsettings, setup_logging

from pyvac.helpers.sqla import create_engine, dispose_engine
from pyvac.models import (
    DBSession, Base, VacationType, Countries,
)


def usage(argv):
    cmd = os.path.basename(argv[0])
    print(('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd)))
    sys.exit(1)


def populate(engine):
    Base.metadata.create_all(engine)
    session = DBSession()

    vactype = VacationType(name='Télétravail')
    session.add(vactype)

    fr_country = Countries.by_name(session, name='fr')
    lu_country = Countries.by_name(session, name='lu')
    us_country = Countries.by_name(session, name='us')
    zh_country = Countries.by_name(session, name='zh')

    # Remote is available for everyone
    vactype.countries.append(fr_country)
    vactype.countries.append(lu_country)
    vactype.countries.append(us_country)
    vactype.countries.append(zh_country)

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


if __name__ == "__main__":
    main()
