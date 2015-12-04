import logging
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


def get_holiday(user, year=None, use_datetime=False):
    """ return holidays for user country

    format is unixtime for javascript
    """
    klass = conv_table[user.country]

    cal = klass()
    current_year = year or datetime.now().year
    # must cast to datetime as workalendar returns only Date objects
    holiday_current = [datetime(dt.year, dt.month, dt.day)
                       for dt, _ in cal.holidays(current_year)]
    if not use_datetime:
        holiday_current = [int(dt.strftime("%s")) * 1000
                           for dt in holiday_current]

    next_year = current_year + 1
    holiday_next = [datetime(dt.year, dt.month, dt.day)
                    for dt, _ in cal.holidays(next_year)]
    if not use_datetime:
        holiday_next = [int(dt.strftime("%s")) * 1000
                        for dt in holiday_next]

    return holiday_current + holiday_next
