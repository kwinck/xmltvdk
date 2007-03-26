#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Køres med ./timefix.py indfil udfil"""

import sys, time

if time.daylight!=0:
    timedif = time.altzone/3600
else:
    timedif = time.timezone/3600
timezone = '%+.2d00' % -timedif

try: data = open(sys.argv[1]).read()
except IOError, message:
    sys.stderr.write(message)
    sys.exit()

def timerepl (match):
    attr, value = match.groups()
    value = value.split()[0] + " " + timezone
    return '%s="%s"' % (attr, value)

import re
data = re.sub(r"(start|stop)\s*=\s*[\"'](.*?)[\"']", timerepl, data)

outfile = open(sys.argv[2], "w")
outfile.write(data)
outfile.close()
