# -*- coding: utf-8 -*-
import sys
import yaml

from celery.signals import worker_process_init
from pyvac.helpers.sqla import create_engine
from pyvac.helpers.ldap import LdapCache
from pyvac.helpers.mail import SmtpCache

try:
    from yaml import CSafeLoader as YAMLLoader
except ImportError:
    from yaml import SafeLoader as YAMLLoader


@worker_process_init.connect
def configure_workers(sender=None, conf=None, **kwargs):
    # The Worker (child process of the celeryd) must have
    # it's own SQL Connection (A unix forking operation preserve fd)
    with open(sys.argv[1]) as fdesc:
        conf = yaml.load(fdesc, YAMLLoader)
    # XXX Register the database
    create_engine('pyvac', conf.get('databases').get('pyvac'),
                  scoped=False)
    LdapCache.configure('pyvac/conf/ldap.yaml')
    SmtpCache.configure(conf.get('smtp'))
