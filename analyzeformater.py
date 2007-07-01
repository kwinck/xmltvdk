#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# $Id$

"""Køres med ./analyzeformater.py fil fil fil ..."""

import sys
from xmltvanalyzer import analyze
from codecs import open
from os import path

# Analyze

rows = []
files = []
filenames = []
pretty = False
wiki=False
debug = "--debug" in sys.argv

sys.stdout.write("Analyzing: ")
for arg in sys.argv[1:]:
    if arg == "--pretty":
        pretty = True
        continue
    if arg == "--wiki":
        wiki=True
        continue
    try: files.append(analyze(arg, debug))
    except: continue
    filenames.append(path.split(arg)[-1])
    sys.stdout.write("#")
    sys.stdout.flush()
rows.append([""])

keys = []
for data, v, x in files:
    for key, z in data.iteritems():
        if not key in keys:
            keys.append(key)
keys.sort()

# Prepare

def header(title):
    rows.append([""])
    rows.append([title])
    for name in filenames:
        rows[-1].append(name)

header("Antal")
for key in keys:
    rows.append([key])
    for data, x, other in files:
        if data.has_key(key):
            rows[-1].append(("%.1f" % (float(data[key])*100/other["progs"])).replace(".",","))
        else: rows[-1].append("")

header("Længde")
for key in keys:
    rows.append([key])
    for data, datatext, x in files:
        if datatext.has_key(key):
            rows[-1].append(("%.1f" % (float(datatext[key])/data[key])).replace(".",","))
        else: rows[-1].append("")

header("Andet")
x, y, dic = files[0]
for k, v in dic.iteritems():
    rows.append([k])
    for x, y, other in files:
        rows[-1].append("%s" % str(other[k]))

# Print

if pretty:
    def il(*lists):
        length = 0
        for l in lists:
            length = max(len(l), length)
        for i in xrange(length):
            data = []
            for l in lists:
                if len(l) > i:
                    data.append(l[i])
                else: data.append(None)
            yield data
    
    widths = []
    for row in rows:
        for cell, i in il(row, range(len(row))):
            if len(widths) <= i:
                widths.append(len(cell))
            else: widths[i] = max(len(cell), widths[i])
    
    for row in rows:
        for cell, i in il(row, range(len(row))):
            sys.stdout.write(cell.ljust(widths[i]+1))
        print
elif wiki:
    def il(*lists):
        length = 0
        for l in lists:
            length = max(len(l), length)
        for i in xrange(length):
            data = []
            for l in lists:
                if len(l) > i:
                    data.append(l[i])
                else: data.append(None)
            yield data
    for row in rows:
        for cell, i in il(row, range(len(row))):
            print "|",cell
        print "|-"
else:
    for row in rows:
        print " ".join(row)
