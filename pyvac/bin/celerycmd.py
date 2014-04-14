#!/usr/bin/python
#-*- coding: utf-8 -*-

from __future__ import absolute_import

import sys

try:
    from celery import Celery
    default_app = Celery()
except ImportError:  # pragma: no cover
    from celery.app import default_app

try:
    from celery.bin.worker import worker as BaseWorkerCommand
except ImportError:  # pragma: no cover
    from celery.bin.celeryd import WorkerCommand as BaseWorkerCommand

try:
    from celery.bin.celery import help as BaseHelp
    from celery.bin.celery import CeleryCommand as BaseCeleryCtl
except ImportError:  # pragma: no cover
    from celery.bin.celeryctl import help as BaseHelp
    from celery.bin.celeryctl import celeryctl as BaseCeleryCtl

from pyvac.config import configure


class CommandMixin(object):
    preload_options = []

    def setup_app_from_commandline(self, argv):
        if len(argv) < 2:
            print >> sys.stderr, 'No configuration file specified.'
            sys.exit(1)

        configure(sys.argv[1], default_app=default_app)

        self.app = default_app
        return argv[:1] + argv[2:]

try:
    from celery.concurrency.processes.forking import freeze_support
except ImportError:  # pragma: no cover
    freeze_support = lambda: True  # noqa


class WorkerCommand(CommandMixin, BaseWorkerCommand):
    preload_options = ()


class Help(BaseHelp):
    option_list = BaseHelp.option_list[len(BaseCeleryCtl.preload_options):]


class CeleryCtl(CommandMixin, BaseCeleryCtl):
    commands = BaseCeleryCtl.commands.copy()
    commands['help'] = Help
    option_list = BaseCeleryCtl.option_list[len(BaseCeleryCtl.preload_options):
                                            ]


def celeryctl():
    return CeleryCtl().execute_from_commandline()


def celeryd():
    freeze_support()
    worker = WorkerCommand()
    worker.execute_from_commandline()


if __name__ == "__main__":
    celeryd()
