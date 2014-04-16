# -*- coding: utf-8 -*-

import os
import sys

from pyramid.paster import get_appsettings, setup_logging

from pyvac.helpers.sqla import create_engine, dispose_engine
from pyvac.models import DBSession, Base, Permission, Group, User

from pyvac.helpers.ldap import LdapCache


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def populate(engine, ldap):

    session = DBSession()

    searchFilter = '(&(objectClass=inetOrgPerson)(employeetype=Employee))'
    required = ['objectClass', 'employeeType', 'cn', 'givenName', 'sn',
                'manager', 'mail', 'ou', 'uid', 'userPassword']

    users = ldap._search(searchFilter, required)
    for user_dn, user_entry in users:
        user_data = ldap.parse_ldap_entry(user_dn, user_entry)
        login = unicode(user_data['login'])
        # check what type of user it is
        group = u'user'
        # if it's a manager members should have him associated as such
        what = '(manager=%s)' % user_data['dn']
        if len(ldap._search(what, None)) > 0:
            group = u'manager'
        # if it's an admin he should be in admin group
        what = '(member=%s)' % user_data['dn']
        if len(ldap._search_admin(what, None)) > 0:
            group = u'admin'

        user = User.by_login(session, login)
        if not user:
            user = User.create_from_ldap(session, user_data, group)
        else:
            # update user with ldap informations in case it changed
            user.email = unicode(user_data['email'])
            user.firstname = unicode(user_data['firstname'])
            user.lastname = unicode(user_data['lastname'])
            user.manager_dn = unicode(user_data['manager_dn'])
            user.dn = unicode(user_data['dn'])
            user.role = group

        session.add(user)

    session.commit()


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)
    config_uri = argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    
    LdapCache.configure(settings['pyvac.ldap.yaml'])
    ldap = LdapCache()

    engine = create_engine('pyvac', settings, scoped=False)
    populate(engine, ldap)
    dispose_engine('pyvac')
