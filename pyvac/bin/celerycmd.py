#!/usr/bin/python
#-*- coding: utf-8 -*-

import sys

try:
    from celery import Celery
    default_app = Celery()
except ImportError:  # pragma: no cover
    from celery.app import default_app

try:
    from celery.bin.worker import worker as BaseWorkerCommand # noqa
except ImportError:  # pragma: no cover
    from celery.bin.celeryd import WorkerCommand as BaseWorkerCommand

from pyvac.config import configure


class CommandMixin(object):
    preload_options = []

    def setup_app_from_commandline(self, argv):
        if len(argv) < 2:
            print('No configuration file specified.', file=sys.stderr)
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


def celeryd():
    freeze_support()
    worker = WorkerCommand()
    worker.execute_from_commandline()


if __name__ == "__main__":
    celeryd()
