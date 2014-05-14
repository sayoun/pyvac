# -*- coding: utf-8 -*-

""" Mock classes for pyvac tasks. """

from .celery import DummyTask

tasks = {
    'worker_approved': DummyTask('worker_approved'),
    'worker_accepted': DummyTask('worker_accepted'),
    'worker_denied': DummyTask('worker_denied'),
}


class DummyTasks(dict):

    @classmethod
    def get(cls, task_name):

        return tasks[task_name]

    def __getitem__(self, key):
        return dict.__getitem__(tasks, key)
