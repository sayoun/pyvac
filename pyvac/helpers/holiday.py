

# import time
import logging
import calendar
from datetime import datetime

from workalendar.europe import France, Luxembourg
from workalendar.usa import California
from workalendar.asia import Taiwan

log = logging.getLogger(__file__)

conv_table = {
    'fr': France,
    'us': California,
    'zh': Taiwan,
    'lu': Luxembourg,
}

override = {}


def init_override(content):
    """Load a yaml file for holidays override.

    You can override holidays for a country and a year through
    usage of a configuration setting:
    pyvac.override_holidays_file = %(here)s/conf/holidays.yaml

    here is a sample:
zh:
  2016:
    '2016-01-01': 'New Years Day'
    '2016-02-07': 'Chinese New Years Eve'
    """
    if not content:
        return
    override.update(content)


def utcify(date):
    """ return an UTC datetime from a Date object """
    return calendar.timegm(date.timetuple()) * 1000


def get_holiday(user, year=None, use_datetime=False):
    """ return holidays for user country

    format is unixtime for javascript
    """
    klass = conv_table[user.country]

    cal = klass()
    current_year = year or datetime.now().year
    next_year = current_year + 1

    # retrieve Dates from workalendar
    holiday_current_raw = [dt for dt, _ in cal.holidays(current_year)]
    holiday_next_raw = [dt for dt, _ in cal.holidays(next_year)]

    if user.country in override and current_year in override[user.country]:
        holiday_current_raw = [datetime.strptime(dt, '%Y-%m-%d')
                               for dt in
                               override[user.country][current_year]]

    if user.country in override and next_year in override[user.country]:
        holiday_next_raw = [datetime.strptime(dt, '%Y-%m-%d')
                            for dt in
                            override[user.country][next_year]]

    if not use_datetime:
        # must cast to javascript timestamp
        holiday_current = [utcify(dt) for dt in holiday_current_raw]
        holiday_next = [utcify(dt) for dt in holiday_next_raw]
    else:
        # must cast to datetime as workalendar returns only Date objects
        holiday_current = [datetime(dt.year, dt.month, dt.day)
                           for dt in holiday_current_raw]
        holiday_next = [datetime(dt.year, dt.month, dt.day)
                        for dt in holiday_next_raw]

    return holiday_current + holiday_next
