# -*- coding: utf-8 -*-

import uuid
import logging
import transaction
from datetime import datetime

from celery.task import Task

from pyvac.models import DBSession, Pool, UserPool


log = logging.getLogger(__name__)


class HeartBeat(Task):
    """
    - close expired pools and create new ones
    - increment user pool amount for all active users
      must check:
      * only one time per month
      * take account of seniority if it applies
      * take account of partial time if it applies
    """
    name = 'heart_beat'

    def process_pool_cycle(self, session):
        """Disable expired pool, create new ones."""
        today = datetime.now().replace(hour=0, minute=0, second=0,
                                       microsecond=0)

        # handle pools cycle expiration
        active_pools = Pool.by_status(session, 'active')
        self.log.debug('found %d active pool' % len(active_pools))
        for pool in active_pools:
            if today >= pool.date_end:
                self.log.info('pool %r must expire: %s' % (pool, pool.date_end)) # noqa
                # retrieve the other pools if pool is in a pool group
                if pool.pool_group:
                    all_pools = Pool.by_pool_group(session, pool.pool_group)
                    restant = [p for p in all_pools if p.name == 'restant'][0]
                    acquis = [p for p in all_pools if p.name == 'acquis'][0]

                    pool_group = uuid.uuid4().hex[:6]
                    new_restant = Pool.clone(session, restant,
                                             date_start=acquis.date_start,
                                             date_end=acquis.date_end,
                                             pool_group=pool_group)
                    new_acquis = Pool.clone(session, acquis, shift=12,
                                            pool_group=pool_group)

                    if pool.country.name == 'lu':
                        initial_amount = 200
                    else:
                        pool_class = acquis.vacation_class
                        initial_amount = pool_class.get_increment_step()

                    # switch current amounts from old acquis to new restant
                    # and grant initial amount for new cycle
                    for up in acquis.user_pools:
                        self.log.debug('user:%s amount:%s' % (up.user.name, up.amount)) # noqa
                        entry = UserPool(amount=0, user=up.user, pool=new_restant) # noqa
                        session.flush()
                        entry.increment(session, up.amount, 'heartbeat')
                        entry = UserPool(amount=0, user=up.user, pool=new_acquis) # noqa
                        session.flush()
                        entry.increment(session, initial_amount, 'heartbeat')

                    restant.expire(session)
                    acquis.expire(session)
                else:
                    # create new pool, shifted by 1 year by default
                    new_pool = Pool.clone(session, pool, shift=12)
                    pool_class = pool.vacation_class
                    initial_amount = pool_class.get_increment_step()
                    for up in pool.user_pools:
                        entry = UserPool(amount=0, user=up.user, pool=new_pool) # noqa
                        session.flush()
                        entry.increment(session, initial_amount, 'heartbeat')
                    pool.expire(session)

    def process_pool_increment(self, session):
        """Increment user pools amount"""
        today = datetime.now()
        active_pools = Pool.by_status(session, 'active')
        self.log.debug('found %d active pool' % len(active_pools))
        for pool in active_pools:
            need_increment = True
            # do we need to increment this pool ?
            # we do this only 1 time per month
            if pool.date_last_increment.month == today.month:
                self.log.info('pool %r already incremented this month' % pool)
                need_increment = False

            pool_to_inc = pool
            if pool.pool_group:
                # if we have a group, only increment acquis not restant
                all_pools = Pool.by_pool_group(session, pool.pool_group)
                acquis = [p for p in all_pools if p.name == 'acquis'][0]
                pool_to_inc = acquis

            for up in pool_to_inc.user_pools:
                up.increment_month(session, need_increment)

            if need_increment:
                pool_to_inc.date_last_increment = today

    def run(self, *args, **kwargs):
        self.log = log
        # init database connection
        session = DBSession()

        # process pool life cycle
        self.process_pool_cycle(session)
        # process user pool increment
        self.process_pool_increment(session)

        session.flush()
        transaction.commit()

        return True
