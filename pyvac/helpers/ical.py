#!/usr/bin/env python
"""
Parse iCalendar
===============

This is the part that, starting from a piece iCalendar,
provides you with the nice dictionary to use further on.

License Info
------------

Copyright (c) 2013, Remigiusz 'lRem' Modrzejewski
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
      * Neither the name of INRIA, I3S, CNRS, UNS, PACA nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL Remigiusz Modrzejewski BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
import icalendar
import re
from datetime import date, datetime
# from time import time


def parse_event(event):
    """
    Return a hash with interesting fields of the `event`.
    """
    ice = icalendar.Calendar.from_ical(event.data)
    # print 'ice %r' % ice
    found = False
    for component in ice.walk():
        if component.name == 'VEVENT':
            assert not found, "Multiple 'VEVENT' fields in event"
            found = True
            ret = parse_single(component)
    assert found, "No 'VEVENT' in event"
    return ret


def parse_calendar(calendar_string):
    """
    Return a list of hashes of interesting fields of events in the calendar.
    """
    ice = icalendar.Calendar.from_ical(calendar_string)
    ret = []
    for component in ice.walk():
        if component.name == 'VEVENT':
            ret.append(parse_single(component))
    return ret


def parse_single(component):
    """
    Parse a single event component.
    """
    # print '-' * 10
    # print 'component', component
    ret = {key: '' for key in ('SUMMARY', 'LOCATION', 'TIME')}
    for key in ret:
        if key in component:
            ret[key] = component[key]
            if key == 'LOCATION':
                ret[key] = re.sub(' *<.*>', '', ret[key])

    for dtkey in ('DTSTART', 'DTEND'):
        if 'DTEND' not in component:
            continue
        if isinstance(component[dtkey].dt, date):
            component[dtkey].dt = datetime.combine(component[dtkey].dt,
                                                   datetime.min.time())

    ret['TIME'] = str(component['DTSTART'].dt.time())
    ret['DTSTART'] = component['DTSTART'].dt.date()
    if 'DURATION' in component:
        ret['DURATION'] = component['DURATION'].dt
        ret['DTEND'] = ret['DTSTART'] + component['DURATION'].dt
    if 'DTEND' in component:
        ret['DTEND'] = component['DTEND'].dt.date()
    ret['EPOCH'] = str(component['DTSTART'].dt.strftime('%s'))
    if 'DESCRIPTION' in component:
        ret.update(parse_description(component['DESCRIPTION']))
    # print 'ret', ret
    return ret


def parse_description(dsc):
    """
    Parse the given string into a hash.
    The string format is `key: value`,
    where key gets converted to upper case
    and value extends until a new line.
    A special last field `Abstract:` extends until the end of string.
    """
    meta, abstract = re.split('abstract:\s*\n*', dsc, flags=re.I)
    ret = {'ABSTRACT': abstract}
    for line in meta.splitlines():
        if ':' in line:
            key, value = re.split('\s*:\s*', line, 1)
            key = key.upper()
            ret[key] = value
    return ret
