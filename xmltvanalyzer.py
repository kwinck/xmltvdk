#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# $Id$

import sys, time, math
from xml.dom import minidom

def plus (dic, key, value=1):
    if dic.has_key(key):
        dic[key] += value
    else: dic[key] = value

def parseTime (s):
    s = s.split()[0]
    return time.mktime(time.strptime(s,"%Y%m%d%H%M%S"))

def analyze (filename, debug = False):
    try: dom = minidom.parse(filename)
    except: raise IOError("%s kunne ikke findes" % filename)
    programmes = dom.getElementsByTagName("programme")
    data = {}
    datatext = {}
    small, big = (0,0)
    last = (0, "")
    chronological = True
    channels = []
    
    for prog in programmes:
        if prog.attributes.has_key("stop"): plus(data, u"stop")

        t = parseTime([v for k,v in prog.attributes.items() if k == "start"][0])
        big = max(t,big)
        if small == 0: small = t
        else: small = min(small,t)

        channel = [v for k,v in prog.attributes.items() if k == "channel"][0]
        if t < last[0] and last[1] == channel:
            chronological = False
            if debug:
                print "Ukronologi ved: %s" % [v for k,v in prog.attributes.items() if k == "start"][0]
        last = (t,channel)
        
        if not channel in channels: channels.append(channel)
        
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
    
    other = {
    "Dage":math.ceil(float(big-small)/60/60/24),
    "progs":len(programmes),
    "Kronologisk":chronological,
    "TeskIAlt":sum([datatext[k] for k in datatext.keys()]),
    "Kanaler":len(channels)}
    
    return (data, datatext, other)

if __name__ == "__main__":
    debug = "--debug" in sys.argv
    data, datatext, other = analyze(sys.argv[1], debug)
    print "            Tag name Count Relative Average Length"
    for key, value in data.iteritems():
        key = key.encode("ascii")
        length = 0
        if key in datatext:
            length = float(datatext[key])/value
        print "%20s %5d %6.1f%%  %5.1f" % (key, value, float(value)*100/other["progs"], length)
    
    for k, v in other.iteritems():
        print "%s\t%s" % (k,str(v))
