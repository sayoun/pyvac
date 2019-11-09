#-*- coding: utf-8 -*-
"""
Initialize a python shell with a given environment (a config file).
"""

import os
import sys

from pyramid.paster import get_appsettings
from pyramid.config import Configurator

from pyvac.helpers.sqla import create_engine
from pyvac.models import DBSession


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
    engine = create_engine('pyvac', settings, scoped=False)

    config = Configurator(settings=settings)
    config.end()

    from pyvac.models import (Base, Permission, Group, User, Request, # noqa
                              Countries, VacationType, PasswordRecovery,
                              Sudoer, CPVacation, RTTVacation,
                              RequestHistory, Pool, UserPool)

    session = DBSession()
    try:
        from IPython import embed
        from IPython.config.loader import Config
        cfg = Config()
        cfg.InteractiveShellEmbed.confirm_exit = False
        embed(config=cfg, banner1="Welcome to pyvac shell.")
    except ImportError:
        import code
        code.interact("pyvac shell", local=locals())


if __name__ == '__main__':
    main()
