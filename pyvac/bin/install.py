# -*- coding: utf-8 -*-

import os
import sys

from pyramid.paster import get_appsettings, setup_logging

from pyvac.helpers.sqla import create_engine, dispose_engine
from pyvac.models import DBSession, Base, Permission, Group, User


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def populate(engine):

    Base.metadata.create_all(engine)
    session = DBSession()

    user_perm = Permission(name=u'user_view')
    admin_perm = Permission(name=u'admin_view')
    manager_perm = Permission(name=u'manager_view')
    session.add(user_perm)
    session.add(admin_perm)
    session.add(manager_perm)

    admin_group = Group(name=u'admin')
    admin_group.permissions.append(user_perm)
    admin_group.permissions.append(admin_perm)
    admin_group.permissions.append(manager_perm)
    session.add(admin_group)

    manager_group = Group(name=u'manager')
    manager_group.permissions.append(user_perm)
    manager_group.permissions.append(manager_perm)
    session.add(manager_group)

    user_group = Group(name=u'user')
    user_group.permissions.append(user_perm)
    session.add(user_group)

    common_password = u'changeme'

    admin = User(login=u'admin',
                 password=common_password,
                 email=u'root@localhost.localdomain',
                 firstname=u'The',
                 lastname=u'Administrator',
                 role=u'admin',
                 country=u'fr')
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
