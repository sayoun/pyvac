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
    user_group = Group.by_name(session, u'user')
    manager_group = Group.by_name(session, u'manager')
    common_password = u'changeme'

    cp_vacation = VacationType.by_name(session, u'CP')
    rtt_vacation = VacationType.by_name(session, u'RTT')

    fr_country = Countries.by_name(session, u'fr')
    us_country = Countries.by_name(session, u'us')

    manager1 = User(login=u'manager1',
                    password=common_password,
                    email=u'manager1@example.net',
                    firstname=u'First',
                    lastname=u'Manager',
                    role=u'manager',
                    _country=fr_country,
                    )
    manager1.groups.append(manager_group)
    session.add(manager1)

    manager2 = User(login=u'manager2',
                    password=common_password,
                    email=u'manager2@example.net',
                    firstname=u'Second',
                    lastname=u'Manager',
                    role=u'manager',
                    _country=fr_country,
                    )
    manager2.groups.append(manager_group)
    session.add(manager2)

    manager_us = User(login=u'manager3',
                      password=common_password,
                      email=u'manager3@example.net',
                      firstname=u'Third',
                      lastname=u'Manager',
                      role=u'manager',
                      _country=us_country,
                      )
    manager_us.groups.append(manager_group)
    session.add(manager_us)

    user1 = User(login=u'jdoe',
                 password=common_password,
                 email=u'jdoe@example.net',
                 manager=manager1,
                 firstname=u'John',
                 lastname=u'Doe',
                 _country=fr_country,
                 )
    user1.groups.append(user_group)
    session.add(user1)

    user2 = User(login=u'janedoe',
                 password=common_password,
                 email=u'janedoe@example.net',
                 manager=manager2,
                 firstname=u'Jane',
                 lastname=u'Doe',
                 _country=fr_country,
                 )
    user2.groups.append(user_group)
    session.add(user2)

    session.flush()
    sudoer = Sudoer(source_id=user2.id, target_id=1)
    session.add(sudoer)

    date_from = datetime.strptime('10/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('14/04/2015', '%d/%m/%Y')
    req1 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=cp_vacation,
                   status=u'PENDING',
                   user=user1,
                   notified=False)
    session.add(req1)

    date_from = datetime.strptime('10/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('21/04/2015', '%d/%m/%Y')
    req2 = Request(date_from=date_from,
                   date_to=date_to,
                   days=10,
                   vacation_type=cp_vacation,
                   status=u'PENDING',
                   user=user2,
                   notified=False,)
    session.add(req2)

    date_from = datetime.strptime('24/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2015', '%d/%m/%Y')
    req3 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=rtt_vacation,
                   status=u'ACCEPTED_MANAGER',
                   user=user1,
                   notified=True,)
    session.add(req3)

    date_from = datetime.strptime('24/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2015', '%d/%m/%Y')
    req4 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=rtt_vacation,
                   status=u'CANCELED',
                   user=user1,
                   notified=True,)
    session.add(req4)

    date_from = datetime.strptime('24/04/2015', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2015', '%d/%m/%Y')
    req5 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   vacation_type=rtt_vacation,
                   status=u'APPROVED_ADMIN',
                   user=manager_us,
                   notified=True,)
    session.add(req5)

    date_from = datetime.strptime('24/08/2011', '%d/%m/%Y')
    date_to = datetime.strptime('24/08/2011', '%d/%m/%Y')
    req6 = Request(date_from=date_from,
                   date_to=date_to,
                   days=0.5,
                   vacation_type=rtt_vacation,
                   status=u'APPROVED_ADMIN',
                   user=user1,
                   notified=True,
                   label=u'AM')
    session.add(req6)

    date_from = datetime.strptime('14/07/2014', '%d/%m/%Y')
    date_to = datetime.strptime('14/07/2014', '%d/%m/%Y')
    req7 = Request(date_from=date_from,
                   date_to=date_to,
                   days=0.5,
                   vacation_type=rtt_vacation,
                   status=u'APPROVED_ADMIN',
                   user=user1,
                   notified=True,
                   label=u'AM')
    session.add(req7)

    # used for rtt vacation checks

    date_from = datetime.strptime('01/04/2016', '%d/%m/%Y')
    date_to = datetime.strptime('02/04/2016', '%d/%m/%Y')
    req8 = Request(date_from=date_from,
                   date_to=date_to,
                   days=1,
                   vacation_type=rtt_vacation,
                   status=u'PENDING',
                   user=user1,
                   notified=True)
    session.add(req8)

    date_from = datetime.strptime('01/03/2016', '%d/%m/%Y')
    date_to = datetime.strptime('02/03/2016', '%d/%m/%Y')
    req9 = Request(date_from=date_from,
                   date_to=date_to,
                   days=1,
                   vacation_type=rtt_vacation,
                   status=u'ACCEPTED_MANAGER',
                   user=user1,
                   notified=True)
    session.add(req9)

    date_from = datetime.strptime('01/02/2016', '%d/%m/%Y')
    date_to = datetime.strptime('02/02/2016', '%d/%m/%Y')
    req10 = Request(date_from=date_from,
                    date_to=date_to,
                    days=1,
                    vacation_type=rtt_vacation,
                    status=u'APPROVED_ADMIN',
                    user=user1,
                    notified=True)
    session.add(req10)

    session.commit()


def tearDownModule():
    dispose_engine()
