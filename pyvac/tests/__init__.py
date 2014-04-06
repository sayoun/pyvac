from datetime import datetime

from pyvac.models import (create_engine, dispose_engine, DBSession,
                          Group,
                          User, Request,
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

    manager1 = User(login=u'manager1',
                    password=common_password,
                    email=u'manager1@example.net',
                    firstname=u'First',
                    lastname=u'Manager',
                    role=u'manager',
                    )
    manager1.groups.append(manager_group)
    session.add(manager1)

    manager2 = User(login=u'manager2',
                    password=common_password,
                    email=u'manager2@example.net',
                    firstname=u'Second',
                    lastname=u'Manager',
                    role=u'manager',
                    )
    manager1.groups.append(manager_group)
    session.add(manager2)

    user1 = User(login=u'jdoe',
                 password=common_password,
                 email=u'jdoe@example.net',
                 manager=manager1,
                 firstname=u'John',
                 lastname=u'Doe',
                 )
    user1.groups.append(user_group)
    session.add(user1)

    user2 = User(login=u'janedoe',
                 password=common_password,
                 email=u'janedoe@example.net',
                 manager=manager2,
                 firstname=u'Jane',
                 lastname=u'Doe',
                 )
    user2.groups.append(user_group)
    session.add(user2)

    date_from = datetime.strptime('10/04/2014', '%d/%m/%Y')
    date_to = datetime.strptime('14/04/2014', '%d/%m/%Y')
    req1 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   type=u'CP',
                   status=u'PENDING',
                   user=user1,
                   notified=False,)
    session.add(req1)

    date_from = datetime.strptime('10/04/2014', '%d/%m/%Y')
    date_to = datetime.strptime('21/04/2014', '%d/%m/%Y')
    req2 = Request(date_from=date_from,
                   date_to=date_to,
                   days=10,
                   type=u'CP',
                   status=u'PENDING',
                   user=user2,
                   notified=False,)
    session.add(req2)

    date_from = datetime.strptime('24/04/2014', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2014', '%d/%m/%Y')
    req3 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   type=u'RTT',
                   status=u'ACCEPTED_MANAGER',
                   user=user1,
                   notified=True,)
    session.add(req3)

    date_from = datetime.strptime('24/04/2014', '%d/%m/%Y')
    date_to = datetime.strptime('28/04/2014', '%d/%m/%Y')
    req4 = Request(date_from=date_from,
                   date_to=date_to,
                   days=5,
                   type=u'RTT',
                   status=u'CANCELED',
                   user=user1,
                   notified=True,)
    session.add(req4)

    session.commit()


def tearDownModule():
    dispose_engine()
