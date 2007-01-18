#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Køres med ./channelid.py [--iso] [--normalize] normalizefil nøglefil indfil udfil"""

import sys
from codecs import open
from xml.dom import minidom

codec = "utf-8"
separator = "\t"
mod = 0

if "--iso" == sys.argv[1]:
	mod += 1
	codec = "iso-8859-1"

if "--normalize" == sys.argv[2]:
	mod = 1+mod
	file = open(sys.argv[3], "r", codec)
	parseDic2 = {}
	for line in file:
		key, value = line.split(separator)
		parseDic2[key.strip()] = value.strip()
	file.close()
	mod = 1+mod
  
file = open(sys.argv[4], "r", codec)
parseDic = {}
for line in file:
	key, value = line.split(separator)
	parseDic[key.strip()] = value.strip()
file.close()
	
dom = minidom.parse(sys.argv[5])

for c in dom.getElementsByTagName("channel"):
	c.attributes["id"].value = parseDic[c.attributes["id"].value]
for p in dom.getElementsByTagName("programme"):
	p.attributes["channel"].value = parseDic[p.attributes["channel"].value]
	
for d in dom.getElementsByTagName("display-name"):
	d.childNodes[0].nodeValue = parseDic2[d.childNodes[0].nodeValue]

outfile = open(sys.argv[6], "w", "utf-8")
outfile.write(dom.toxml())
outfile.close()
