# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime

from pyramid.paster import get_appsettings, setup_logging

from pyvac.helpers.sqla import create_engine, dispose_engine
from pyvac.models import (
    DBSession, Base, Permission, Group, User, VacationType, Countries,
    Pool,
)


def usage(argv):
    cmd = os.path.basename(argv[0])
    print(('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd)))
    sys.exit(1)


def populate(engine):

    Base.metadata.create_all(engine)
    session = DBSession()

    user_perm = Permission(name='user_view')
    admin_perm = Permission(name='admin_view')
    manager_perm = Permission(name='manager_view')
    sudo_perm = Permission(name='sudo_view')
    session.add(user_perm)
    session.add(admin_perm)
    session.add(manager_perm)
    session.add(sudo_perm)

    admin_group = Group(name='admin')
    admin_group.permissions.append(user_perm)
    admin_group.permissions.append(admin_perm)
    admin_group.permissions.append(manager_perm)
    admin_group.permissions.append(sudo_perm)
    session.add(admin_group)

    manager_group = Group(name='manager')
    manager_group.permissions.append(user_perm)
    manager_group.permissions.append(manager_perm)
    manager_group.permissions.append(sudo_perm)
    session.add(manager_group)

    user_group = Group(name='user')
    user_group.permissions.append(user_perm)
    session.add(user_group)

    sudoer_group = Group(name='sudoer')
    sudoer_group.permissions.append(sudo_perm)
    session.add(sudoer_group)

    vactype1 = VacationType(name='CP')
    session.add(vactype1)
    vactype2 = VacationType(name='RTT')
    session.add(vactype2)
    vactype3 = VacationType(name='Congé Parental')
    session.add(vactype3)
    vactype4 = VacationType(name='Récupération')
    session.add(vactype4)
    vactype5 = VacationType(name='Maladie', visibility='admin')
    session.add(vactype5)
    vactype6 = VacationType(name='Exceptionnel')
    session.add(vactype6)
    vactype7 = VacationType(name='Compensatoire')
    session.add(vactype7)
    vactype8 = VacationType(name='Télétravail')
    session.add(vactype8)

    fr_country = Countries(name='fr')
    session.add(fr_country)
    lu_country = Countries(name='lu')
    session.add(lu_country)
    us_country = Countries(name='us')
    session.add(us_country)
    zh_country = Countries(name='zh')
    session.add(zh_country)

    now = datetime.now()
    cp_pool1 = Pool(name='acquis',
                    date_start=datetime(now.year, 6, 1),
                    date_end=datetime(now.year + 1, 5, 31),
                    status='active',
                    vacation_type=vactype1,
                    country=fr_country,
                    pool_group=1,
                    date_last_increment=now,
                    )
    session.add(cp_pool1)
    cp_pool2 = Pool(name='restant',
                    date_start=datetime(now.year - 1, 6, 1),
                    date_end=datetime(now.year, 5, 31),
                    status='active',
                    vacation_type=vactype1,
                    country=fr_country,
                    pool_group=1,
                    date_last_increment=now,
                    )
    session.add(cp_pool2)
    cplu_pool1 = Pool(name='acquis',
                      alias='légaux',
                      date_start=datetime(now.year, 1, 1),
                      date_end=datetime(now.year + 1, 3, 31),
                      status='active',
                      vacation_type=vactype1,
                      country=lu_country,
                      pool_group=2,
                      date_last_increment=now,
                      )
    session.add(cplu_pool1)
    cplu_pool2 = Pool(name='restant',
                      alias='report',
                      date_start=datetime(now.year - 1, 1, 1),
                      date_end=datetime(now.year, 3, 31),
                      status='active',
                      vacation_type=vactype1,
                      country=lu_country,
                      pool_group=2,
                      date_last_increment=now,
                      )
    session.add(cplu_pool2)
    rtt_pool = Pool(name=vactype2.name,
                    date_start=datetime(now.year, 1, 1),
                    date_end=datetime(now.year + 1, 12, 31),
                    status='active',
                    vacation_type=vactype2,
                    country=fr_country,
                    date_last_increment=now,
                    )
    session.add(rtt_pool)

    # CP is available for everyone
    vactype1.countries.append(fr_country)
    vactype1.countries.append(lu_country)
    vactype1.countries.append(us_country)
    vactype1.countries.append(zh_country)

    # RTT only available for france
    vactype2.countries.append(fr_country)

    # Parental vacation is available for everyone
    vactype3.countries.append(fr_country)
    vactype3.countries.append(lu_country)
    vactype3.countries.append(us_country)
    vactype3.countries.append(zh_country)

    # Recovery is available for everyone
    vactype4.countries.append(fr_country)
    vactype4.countries.append(lu_country)
    vactype4.countries.append(us_country)
    vactype4.countries.append(zh_country)

    # Sickness vacation is available for all countries
    vactype5.countries.append(fr_country)
    vactype5.countries.append(lu_country)
    vactype5.countries.append(us_country)
    vactype5.countries.append(zh_country)

    # Exception vacation is available for all countries
    vactype6.countries.append(fr_country)
    vactype6.countries.append(lu_country)
    vactype6.countries.append(us_country)
    vactype6.countries.append(zh_country)

    # Holiday recovery is only available for LU
    vactype7.countries.append(lu_country)

    # Remote is available for everyone
    vactype8.countries.append(fr_country)
    vactype8.countries.append(lu_country)
    vactype8.countries.append(us_country)
    vactype8.countries.append(zh_country)

    common_password = 'changeme'

    admin = User(login='admin',
                 password=common_password,
                 email='root@localhost.localdomain',
                 firstname='The',
                 lastname='Administrator',
                 role='admin',
                 _country=fr_country)
    admin.groups.append(admin_group)
    session.add(admin)

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
