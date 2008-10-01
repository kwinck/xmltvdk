#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Adds missing timezone information to xmltv files.
#
# ----------------------------------------------------------------------------
# "THE BEER-WARE LICENSE" (Revision 42):
# http://svalgaard.net/jens/ wrote this file. As long as you retain
# this notice you can do whatever you want with this stuff. If we
# meet some day, and you think this stuff is worth it, you can buy me
# a beer in return, Jens Svalgaard Kohrt
# ----------------------------------------------------------------------------
#
# (c) 2008 http://svalgaard.net/jens/
#
VERSION = "$Id$"

import datetime
import optparse
import re
import sys
import time
try:
    # see: http://pytz.sourceforge.net/
    import pytz
    mytz = pytz.timezone("Europe/Copenhagen")
except ImportError:
    mytz = None

def splitTimeStamp(ts):
    '''splitTS(ts) -> prefix of a time tuple 
    (tm_year,tm_mon,tm_mday,tm_hour,tm_min,tm_sec)

Split time stamp assuming that it uses one of the formats
    "%Y%m%d%H%M%S" or "%Y%m%d%H%M".

Example:
   getTimeZone("20080723054000") -> (2008,7,23,5,40,0)

'''
    assert(len(ts) in [12,14])
    tss = [int(ts[i:i+2]) for i in range(2, len(ts),2)]
    tss[0] += int(ts[:2])*100

    return tuple(tss)

def _getTimeZoneOffset(ts, is_dst = -1):
    '''_getTimeZoneOffset(timestamp, is_dst) -> timezone offset in seconds

Returns None if the timezone cannot be found.

Try to find timezone of timestamp according the whatever timezone
time.localtime uses.

is_dst is used to determine the correct timezone in the ambigous
period at the end of daylight savings time (set the value to True or
False): If you are not sure: leave it alone.

On a properly configured system, this should give the right outcome
(except possibly in the short time window when changing from summer to
winter time).

Example:
   getTimeZone("20080723054000") -> 3600
'''
    if is_dst < 0:
        z = -1
    else:
        z = int(bool(is_dst)) # ensure a 0 or 1 value

    # split time stamp and put the pieces together
    tss = splitTimeStamp(ts)
    tss += (0,)*(8-len(tss)) + (z,)

    z = time.localtime(time.mktime(tuple(tss)))[-1]
    return [-time.timezone, -time.altzone, None][z]

def getTimeZone(ts, is_dst = -1):
    '''getTimeZone(timestamp, is_dst) -> timezone string

Returns None if the timezone cannot be found.

is_dst is used to determine the correct timezone in the ambigous
period at the end of daylight savings time (set the value to True or
False): If you are not sure: leave it alone.

On a properly configured system, this should give the right outcome
(except possibly in the short time window when changing from summer to
winter time).

This uses pytz if available, otherwise getTimeZoneOffset (i.e., the
time module).

Example:
   getTimeZone("20080723054000") -> "+0200"
'''
    global mytz

    if mytz:
        tss = splitTimeStamp(ts)
        try:
            dt = datetime.datetime(*tss)
            ldt = mytz.localize(dt, is_dst)
            return ldt.strftime("%z")
        except IndexError:
            # is returned only for non-existing points in time, e.g.
            # at 2:30 when changing from winter to summer time.
            return None
    else:
        offset = _getTimeZoneOffset(ts, is_dst)
        if offset is None:
            return None
        return "%+03d%02d" % divmod(offset//60,60)

class LocalTimeZone(datetime.tzinfo):
    "Use timezone information according to the module time"
    def __init__(self, is_dst = -1):
        datetime.tzinfo.__init__(self)
        if is_dst == -1:
            self.is_dst = -1
        else:
            self.is_dst = int(bool(is_dst)) # ensure a 0 or 1 value

    def _dtOffset(self, dt):
        dtt = dt.replace(tzinfo = None).timetuple()[:-1] + (self.is_dst,)
        tst = time.localtime(time.mktime(dtt))
        return [-time.timezone, -time.altzone, None][tst[-1]]
    
    def utcoffset(self, dt):
        offset = self._dtOffset(dt)
        if offset is None: return None
        return datetime.timedelta(0,offset)
    
    def dst(self, dt):
        offset = self._dtOffset(dt)
        if offset is None: return None
        return datetime.timedelta(0,offset+time.timezone)
    
    def localize(self, dt, is_dst = -1):
        return dt.replace(tzinfo = LocalTimeZone(is_dst))
    
def testTimeZone():
    global mytz
    mytz_restore = mytz
    ecount = 0
    for round in range(4):
        if round == 0:
            print "Testing using pytz"
            if mytz is None:
                print "Pytz is not available..."
                continue
        elif round == 1:
            print "Testing using LocalTimeZone"
            mytz = LocalTimeZone()
        elif round == 2:
            print "Testing using time module directly"
            mytz = None
        else:
            mytz = mytz_restore
            break
        for (v,expected) in [
            # Summer time
            (("20080723054000",),"+0200"),
            (("200807230540",),"+0200"),
            # Winter time
            (("20081123054000",),"+0100"),
            (("200811230540",),"+0100"),
            #
            # Summer time
            (("200810260130",),"+0200"),      # summer time
            (("200810260130",True),"+0200"),  # summer time
            (("200810260130",False),"+0200"), # summer time
            # Last minute of summer time
            (("200810260159",),"+0200"),
            (("200810260159",True),"+0200"),
            (("200810260159",False),"+0200"),
            # Either summer or winter time (ambiguous)
            (("200810260200",),"None - either value is fine"),
            (("200810260200",True),"+0200"),
            (("200810260200",False),"+0100"),
            # Either summer or winter time (ambiguous)
            (("200810260230",),"None - either value is fine"),
            (("200810260230",True),"+0200"), 
            (("200810260230",False),"+0100"),
            #
            (("200810260300",),"+0100"),   # start of unambiguous winter time
            # 
            (("200810260301",),"+0100"),     # winter time
            (("200810260301",True),"+0100"),
            (("200810260301",False),"+0100"),
            #
            (("200903290159",),"+0100"),   # last minute of winter time
            (("200903290159",True),"+0100"),   # last minute of winter time
            (("200903290159",False),"+0100"),   # last minute of winter time
            #
            (("200903290230",), "None - illegal time does not exist"),
            (("200903290230",True),"None - illegal time does not exist"),
            (("200903290230",False), "None - illegal time does not exist"),
            #
            (("200903290300",),"+0200"),   # first minute of summer time
            (("200903290300",True),"+0200"),   # first minute of summer time
            (("200903290300",False),"+0200"),   # first minute of summer time
            ]:
            f = getTimeZone(*v)
            if f == expected or expected[0] in "+-":
                print "OK     %-23s -> %s" % (v,f)
            elif expected[0] not in "+1":
                print "OK     %-23s -> %s (expected: %s)" % (v,f,expected)
            else:
                print "ERROR? %-23s -> %s (expected: %s)" % (v,f,expected)
                ecount += 1
                
    print
    print "Errors found: %d" % ecount
    mytz = mytz_restore
    return ecount

def fixTimeZone(xml):
    '''Add missing timezone information to xml.'''
    
    def timerepl (match):
        pre, ts, post = match.groups()
        ts = ts.strip()
        if "+" not in ts and len(ts) in [12,14]:
            ts += " " + getTimeZone(ts)
        return pre + ts + post
    
    return re.sub(r"((?:start|stop)\s*=\s*[\"'])(.*?)([\"'])", timerepl, xml)


def main():
    global VERSION

    parser = optparse.OptionParser()
    parser.usage = "%prog [options] [xmltv-inputfile [xmltv-outputfile]] "

    # general options
    parser.add_option("-t", "--test", dest="test", action="store_true",
                      default=False,
                      help="Test time zone data (do not read xml-files).")
    parser.add_option("-v", "--version", dest="version", action="store_true",
                      default=False,
                      help="Show version information and quit.")
    parser.add_option("-o","--output", dest="output", metavar="FILENAME",
                      default=None,
                      help=("File name of output xml file. If not provided "
                            "or '-', stdout is used."))

    options, args = parser.parse_args()
    
    if options.test:
        n = testTimeZone()
        sys.exit(n)
    
    if options.version:
        print "timefix from xmltvdk, version", VERSION
        sys.exit(0)

    if len(args) > 3:
        parser.error("You can supply at most two file names")

    if len(args) == 2:
        if options.output is not None:
            parser.error("You cannot BOTH specify the output file directly "
                         "AND use '--output'")
        else:
            options.output = args[1]

    if len(args) >= 1:
        xml = open(args[0]).read()
    else:
        xml = sys.stdin.read()
    
    xml = fixTimeZone(xml)

    # write result
    if options.output not in [None, "-"]:
        fd = open(options.output,"w")
    else:
        fd = sys.stdout

    fd.write(xml)

if __name__ == "__main__":
    main()
