#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Køres med ./channelid.py nøglefil indfil udfil"""

separator = "\t"

#deprecated
mod = 0
import sys
if "--iso" == sys.argv[1]:
    mod += 1

#     -----     Henter filer     -----     #

try:
    data = open(sys.argv[2+mod]).read()
    pfile = open(sys.argv[1+mod]).read()
except IOError, message:
    sys.stderr.write(str(message))
    sys.exit()

for codec in ("utf-8", "iso-8859-1"):
    try: pfile = pfile.decode(codec)
    except: continue
    break

for codec in ("utf-8", "iso-8859-1"):
    try:
        data.decode(codec)
        pfile = pfile.encode(codec)
    except: continue
    break

#     -----     Parsefile parsing     -----     #

parseDic = {}
for line in pfile.splitlines():
    if not line.strip(): continue
    key, value = line.split(separator)
    parseDic[key.strip()] = value.strip()

#     -----     Xmlfile parsing     -----     #

def chanrepl (match):
    attr, value = match.groups()
    if value in parseDic:
        return '%s="%s"' % (attr, parseDic[value])
    return match.group()

import re
data = re.sub(r"(id|channel)\s*=\s*[\"'](.*?)[\"']", chanrepl, data)

outfile = open(sys.argv[3+mod], "w")
outfile.write(data)
outfile.close()
