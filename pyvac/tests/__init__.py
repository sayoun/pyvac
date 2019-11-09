# -*- coding: utf-8 -*-
from datetime import datetime

from pyvac.models import (create_engine, dispose_engine, DBSession,
                          Group,
                          User, Request, VacationType, Countries, Sudoer,
                          )
from pyvac.bin.install import populate
from .conf import settings


def setUpModule():

    engine = create_engine(settings)
    populate(engine)

    session = DBSession()
    user_group = Group.by_name(session, 'user')
    manager_group = Group.by_name(session, 'manager')
    sudoer_group = Group.by_name(session, 'sudoer')
    common_password = 'changeme'

    cp_vacation = VacationType.by_name(session, 'CP')
    rtt_vacation = VacationType.by_name(session, 'RTT')
    recovery_vacation = VacationType.by_name(session, 'Récupération')
    sickness_vacation = VacationType.by_name(session, 'Maladie')
    exception_vacation = VacationType.by_name(session, 'Exceptionnel')

    fr_country = Countries.by_name(session, 'fr')
    us_country = Countries.by_name(session, 'us')
    lu_country = Countries.by_name(session, 'lu')

    manager1 = User(login='manager1',
                    password=common_password,
                    email='manager1@example.net',
                    firstname='First',
                    lastname='Manager',
                    role='manager',
                    _country=fr_country,
                    )
    manager1.groups.append(manager_group)
    session.add(manager1)

    manager2 = User(login='manager2',
                    password=common_password,
                    email='manager2@example.net',
                    firstname='Second',
                    lastname='Manager',
                    role='manager',
                    _country=fr_country,
                    )
    manager2.groups.append(manager_group)
    session.add(manager2)

    manager_us = User(login='manager3',
                      password=common_password,
                      email='manager3@example.net',
                      firstname='Third',
                      lastname='Manager',
                      role='manager',
                      _country=us_country,
                      )
    manager_us.groups.append(manager_group)
    session.add(manager_us)

    user1 = User(login='jdoe',
                 password=common_password,
                 email='jdoe@example.net',
                 manager=manager1,
                 firstname='John',
                 lastname='Doe',
                 _country=fr_country,
                 registration_number=1337,
                 )
    user1.groups.append(user_group)
    session.add(user1)

    user2 = User(login='janedoe',
                 password=common_password,
                 email='janedoe@example.net',
                 manager=manager2,
                 firstname='Jane',
                 lastname='Doe',
                 _country=fr_country,
                 )
    user2.groups.append(user_group)
    user2.groups.append(sudoer_group)
    session.add(user2)

    session.flush()
    sudoer = Sudoer(source_id=user2.id, target_id=1)
    session.add(sudoer)

    user3 = User(login='sarah.doe',
                 password=common_password,
                 email='sarah@example.net',
                 manager=manager1,
                 firstname='Sarah',
                 lastname='Doe',
                 _country=lu_country,
                 )
    user3.groups.append(user_group)
    session.add(user3)

    date_from = datetime.strptime('10/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('14/04/2015', '%d/%m/%Y')
    req1 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=cp_vacation,
                   status='PENDING',
                   user=user1,
                   notified=False)
    session.add(req1)

    date_from = datetime.strptime('10/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('21/04/2015', '%d/%m/%Y')
    req2 = Request(date_from=date_from,
                   date_to=date_to,
                   days=10,
                   vacation_type=cp_vacation,
                   status='PENDING',
                   user=user2,
                   notified=False,)
    session.add(req2)

    date_from = datetime.strptime('24/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2015', '%d/%m/%Y')
    req3 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=rtt_vacation,
                   status='ACCEPTED_MANAGER',
                   user=user1,
                   notified=True,)
    session.add(req3)

    date_from = datetime.strptime('24/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2015', '%d/%m/%Y')
    req4 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=rtt_vacation,
                   status='CANCELED',
                   user=user1,
                   notified=True,)
    session.add(req4)

    date_from = datetime.strptime('24/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2015', '%d/%m/%Y')
    req5 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=rtt_vacation,
                   status='APPROVED_ADMIN',
                   user=manager_us,
                   notified=True,)
    session.add(req5)

    date_from = datetime.strptime('24/08/2011', '%d/%m/%Y')
    date_to = datetime.strptime('24/08/2011', '%d/%m/%Y')
    req6 = Request(date_from=date_from,
                   date_to=date_to,
                   days=0.5,
                   vacation_type=rtt_vacation,
                   status='APPROVED_ADMIN',
                   user=user1,
                   notified=True,
                   label='AM')
    session.add(req6)

    date_from = datetime.strptime('14/07/2014', '%d/%m/%Y')
    date_to = datetime.strptime('14/07/2014', '%d/%m/%Y')
    req7 = Request(date_from=date_from,
                   date_to=date_to,
                   days=0.5,
                   vacation_type=rtt_vacation,
                   status='APPROVED_ADMIN',
                   user=user1,
                   notified=True,
                   label='AM')
    session.add(req7)

    # used for rtt vacation checks

    date_from = datetime.strptime('01/04/2016', '%d/%m/%Y')
    date_to = datetime.strptime('02/04/2016', '%d/%m/%Y')
    req8 = Request(date_from=date_from,
                   date_to=date_to,
                   days=1,
                   vacation_type=rtt_vacation,
                   status='PENDING',
                   user=user1,
                   notified=True)
    session.add(req8)

    date_from = datetime.strptime('01/03/2016', '%d/%m/%Y')
    date_to = datetime.strptime('02/03/2016', '%d/%m/%Y')
    req9 = Request(date_from=date_from,
                   date_to=date_to,
                   days=1,
                   vacation_type=rtt_vacation,
                   status='ACCEPTED_MANAGER',
                   user=user1,
                   notified=True)
    session.add(req9)

    date_from = datetime.strptime('01/02/2016', '%d/%m/%Y')
    date_to = datetime.strptime('02/02/2016', '%d/%m/%Y')
    req10 = Request(date_from=date_from,
                    date_to=date_to,
                    days=1,
                    vacation_type=rtt_vacation,
                    status='APPROVED_ADMIN',
                    user=user1,
                    notified=True)
    session.add(req10)

    date_from = datetime.strptime('01/06/2016', '%d/%m/%Y')
    date_to = datetime.strptime('02/06/2016', '%d/%m/%Y')
    req11 = Request(date_from=date_from,
                    date_to=date_to,
                    days=1,
                    vacation_type=recovery_vacation,
                    status='APPROVED_ADMIN',
                    user=user1,
                    notified=True)
    session.add(req11)

    date_from = datetime.strptime('12/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('12/04/2015', '%d/%m/%Y')
    req12 = Request(date_from=date_from,
                    date_to=date_to,
                    days=1,
                    vacation_type=rtt_vacation,
                    status='DENIED',
                    user=user1,
                    notified=True)
    session.add(req12)

    date_from = datetime.strptime('06/06/2016', '%d/%m/%Y')
    date_to = datetime.strptime('06/06/2016', '%d/%m/%Y')
    req13 = Request(date_from=date_from,
                    date_to=date_to,
                    days=1,
                    vacation_type=sickness_vacation,
                    status='APPROVED_ADMIN',
                    user=user1,
                    notified=True)
    session.add(req13)

    date_from = datetime.strptime('13/06/2016', '%d/%m/%Y')
    date_to = datetime.strptime('13/06/2016', '%d/%m/%Y')
    req14 = Request(date_from=date_from,
                    date_to=date_to,
                    days=1,
                    vacation_type=exception_vacation,
                    status='APPROVED_ADMIN',
                    user=user2,
                    message="I need to see Star Wars, I'm a huge fan",
                    notified=True)
    session.add(req14)

    session.commit()


def tearDownModule():
    dispose_engine()
