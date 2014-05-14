# -*- coding: utf-8 -*-

""" Mock classses for Celery subtask method and Task class. """


def subtask(task):
    return task


class DummyTask(object):

    _ids = {
        'worker_approved': 10,
        'worker_accepted': 20,
        'worker_denied': 30,
    }

    def __init__(self, task=None):
        self.task = task

    @property
    def task_id(self):
        return self._ids[self.task]

    @property
    def name(self):
        return self.task

    def delay(self, **kwargs):
        return self

    def apply_async(self, **kwargs):
        return self

    def send(self, **kwargs):
        return True
