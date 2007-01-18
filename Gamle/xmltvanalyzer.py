#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from xml.dom import minidom

def plus (dic, key, value=1):
    if dic.has_key(key):
        dic[key] += value
    else: dic[key] = value

dom = minidom.parse(sys.argv[1])
programmes = dom.getElementsByTagName("programme")
data = {}
datatext = {}
for prog in programmes:
    if prog.attributes.has_key("stop"): plus(data, u"stop")
    for node in prog.childNodes:
        if node.nodeType != node.ELEMENT_NODE:
            continue;
        name = node.nodeName;
        if node.attributes.has_key("lang"):
            name += node.attributes["lang"].value
        plus(data, name)
        if len(node.childNodes) == 1 and \
                node.firstChild.nodeType == node.TEXT_NODE:
            plus(datatext, name, len(node.firstChild.wholeText))
        else:
            plus(datatext, name, len([n for n in node.childNodes if not n.nodeType == node.TEXT_NODE]))

print "            Tag name Count Relative Average Length"
for key, value in data.iteritems():
    key = key.encode("ascii")
    length = 0
    if key in datatext:
        length = float(datatext[key])/value
    print "%20s %5d %6.1f%%  %5.1f" % (key, value,  float(value)*100/len(programmes), length)
print "Tekst i alt: %d" % sum([datatext[k] for k in datatext.keys()])