# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from .base import View, CreateView, EditView, DeleteView
from pyvac.models import Pool, Countries, VacationType

log = logging.getLogger(__name__)


class List(View):
    """
    List pools
    """
    def render(self):
        pools = Pool.by_status(self.session, 'active')
        pastpools = Pool.by_status(self.session, ['inactive', 'expired'])
        return {'pools': pools, 'pastpools': pastpools}


class PoolMixin:
    model = Pool
    matchdict_key = 'pool_id'
    redirect_route = 'list_pools'

    def update_view(self, model, view):
        view['countries'] = Countries.all(self.session,
                                          order_by=Countries.name)
        view['vacation_types'] = VacationType.all(self.session,
                                                  order_by=VacationType.id)

        if view['errors']:
            self.request.session.flash('error;%s' % ','.join(view['errors']))

    def set_country(self, pool):
        r = self.request
        pool.country_id = r.params['set_country']

    def set_vacation_type(self, pool):
        r = self.request
        pool.vacation_type_id = r.params['set_vacation_type']

    def set_dates(self, pool):
        r = self.request
        pool.date_start = datetime.strptime(r.params['date_start'], '%d/%m/%Y') # noqa
        pool.date_end = datetime.strptime(r.params['date_end'], '%d/%m/%Y') # noqa

    def validate(self, model, errors):
        r = self.request
        date_start = None
        date_end = None
        try:
            date_start = datetime.strptime(r.params['date_start'], '%d/%m/%Y')
        except:
            errors.append('invalid date_start')
        try:
            date_end = datetime.strptime(r.params['date_end'], '%d/%m/%Y')
        except:
            errors.append('invalid date_end')
        # check that it's unique
        if date_start and date_end:
            where = (Pool.date_start == date_start,
                     Pool.date_end == date_end,
                     Pool.vacation_type_id == r.params['set_vacation_type'],
                     Pool.country_id == r.params['set_country'])
            exists = Pool.find(self.session, where=where)
            if exists:
                errors.append('There is already a Pool for these parameters')
        if errors:
            self.request.session.flash('error;%s' % ','.join(errors))
        return len(errors) == 0


class Create(PoolMixin, CreateView):
    """
    Create pool
    """
    def save_model(self, pool):
        super(Create, self).save_model(pool)
        self.set_country(pool)
        self.set_vacation_type(pool)
        self.set_dates(pool)


class Edit(PoolMixin, EditView):
    """
    Edit pool
    """
    def save_model(self, pool):
        super(Edit, self).save_model(pool)
        self.set_country(pool)
        self.set_vacation_type(pool)
        self.set_dates(pool)


class Delete(PoolMixin, DeleteView):
    """
    Delete pool
    """

    def delete(self, pool):
        # disable this pool
        pool.status = 'inactive'
