# -*- coding: utf-8 -*-
import logging
from .base import View
from pyvac.helpers.holiday import get_holiday

log = logging.getLogger(__name__)


class List(View):
    """
    List holiday for given year
    """
    def render(self):
        year = int(self.request.params.get('year'))
        holidays = get_holiday(self.user, year)
        return holidays
