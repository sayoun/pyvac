from __future__ import absolute_import

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


override = {'zh': {2016: [('2016-01-01', 'New Years Day'),
                          ('2016-02-07', 'Chinese New Years Eve'),
                          ('2016-02-08', 'Chinese New Years Day'),
                          ('2016-02-09', 'Chinese New Year Holiday 1'),
                          ('2016-02-10', 'Chinese New Year Holiday 2'),
                          ('2016-02-11', 'Chinese New Year Holiday 3'),
                          ('2016-02-12', 'Chinese New Year Holiday 4'),
                          ('2016-02-29', '228 Memorial Day (observed)'),
                          ('2016-04-04', 'Childrens Day'),
                          ('2016-04-05', 'Tomb Sweeping Day'),
                          ('2016-06-09', 'Dragon Boat Festival'),
                          ('2016-09-15', 'Mid-Autumn Festival'),
                          ('2016-09-15', 'Mid-Autumn Festival'),
                          ('2016-09-16', 'Mid-Autumn Festival (observance)'),
                          ('2016-10-10', 'National Day')],
                   2017: [('2017-01-01', 'Lunar new year'),
                          ('2017-01-01', 'New year'),
                          ('2017-01-27', "Chinese New Year's Eve"),
                          ('2017-01-28', 'Chinese New Year'),
                          ('2017-01-29', 'Chinese New Year'),
                          ('2017-01-30', 'Chinese New Year'),
                          ('2017-02-27', '228 Peace Memorial Day'),
                          ('2017-02-28', '228 Peace Memorial Day'),
                          ('2017-04-03', "Children's Day"),
                          ('2017-04-04', "Combination of Women's Day and Children's Day"), # noqa
                          ('2017-04-04', 'Qingming Festival'),
                          ('2017-05-01', '1st May'),
                          ('2017-05-29', 'Dragon Boat Festival'),
                          ('2017-05-30', 'Dragon Boat Festival'),
                          ('2017-10-04', 'Mid-Autumn Festival'),
                          ('2017-10-09', 'National Day/Double Tenth Day'),
                          ('2017-10-10', 'National Day/Double Tenth Day')],
                   2018: [('2018-01-01', 'New year'),
                          ('2018-02-15', "Chinese New Year's eve"),
                          ('2018-02-16', 'Chinese New Year'),
                          ('2018-02-17', 'Chinese New Year (2nd day)'),
                          ('2018-02-18', 'Chinese New Year (3rd day)'),
                          ('2018-02-19', 'Chinese New Year (4th day)'),
                          ('2018-02-20', 'Chinese New Year (5th day)'),
                          ('2018-02-28', '228 Peace Memorial Day'),
                          ('2018-04-04', "Combination of Women's Day and Children's Day"), # noqa
                          ('2018-04-05', 'Qingming Festival'),
                          ('2018-04-06', 'Qingming Festival'),
                          ('2018-05-01', '1st May'),
                          ('2018-06-18', 'Dragon Boat Festival'),
                          ('2018-09-24', 'Mid-Autumn Festival'),
                          ('2018-10-10', 'National Day/Double Tenth Day'),
                          ('2018-12-31', "New Year's Eve")],
            }}


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
                               for dt, _ in
                               override[user.country][current_year]]

    if user.country in override and next_year in override[user.country]:
        holiday_next_raw = [datetime.strptime(dt, '%Y-%m-%d')
                            for dt, _ in
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
