#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Køres med ./xmltvtitle.py indfil udfil"""

import sys
from xml.dom import minidom
from xml.parsers.expat import ExpatError

file1 = None

try: file1 = minidom.parse(sys.argv[1])
except IOError: sys.stderr.write("Fil 1 (%s) kunne ikke findes\n" % sys.argv[1])
except ExpatError, message: sys.stderr.write(sys.argv[1]+" "+str(message)+"\n")

from shutil import copy

# ---------- ---------- Funktioner ---------- ---------- #

def tagname (node):
    '''Modtager f.eks. en <title lang="da"> node, og returnerer ("titleda",<title...>)'''
    tagname = node.tagName
    tagname += "".join([v.value for v in node.attributes.values()])
    return (tagname, node)

def tagdir (nodes):
    '''Laver dic {name:<node>} over <node>s i liste'''
    dic = {}
    for n in nodes:
        if n.nodeType == n.TEXT_NODE: continue
        dic[tagname(n)[0]] = n
    return dic

# ---------- ---------- Funktioner ---------- ---------- #

import time
def parseTime (s):
    '''Oversætter fra xmltv's tidsformat til unixtimestamp'''
    s = s.split()[0]
    # Fixme: Hvis en grabber udnytter sig af dtd'ens mulighed for f.eks. kun at specificere %Y%m, vil strptime kommer med fejl. Det er der ingen af dem, der gør.
    if len(s)==12:
        return time.mktime(time.strptime(s,"%Y%m%d%H%M")) 
    else:
        return time.mktime(time.strptime(s,"%Y%m%d%H%M%S")) 

def notime (programme):
    '''Tester om et program starter tidligere eller samtidigt med, at det slutter'''
    if not programme.attributes.has_key("stop"):
        return False
    elif programme.attributes["stop"].value == "":
        return False
    t_start = parseTime(programme.attributes["start"].value)
    t_end = parseTime(programme.attributes["stop"].value)
    return t_end <= t_start

def getFileProgrammes (file):
    '''Laver {"channelid":[programmes]} fra en dom'''
    fileProgrammes = {}
    for programme in file.getElementsByTagName("programme"):
        if notime(programme):
            continue
        channel = programme.attributes["channel"].value
        if not channel in fileProgrammes:
            fileProgrammes[channel] = [programme]
        else: fileProgrammes[channel].append(programme)
    return fileProgrammes

# ---------- ---------- Merger <programme> tags  ---------- ---------- #

file1Programmes = getFileProgrammes(file1)

#Checker programmer
for channel, f1progs in file1Programmes.iteritems():
    print "Channel: ", channel
    for f1prog in f1progs:
        #Overføring af manglende tags + overføring af tags med flest childnodes
        file1tagnames = tagdir(f1prog.childNodes)
        if file1tagnames.has_key("title") and file1tagnames.has_key("titleda"):
            titleDaNode=file1tagnames["titleda"]
            f1prog.removeChild(titleDaNode)
            if file1tagnames.has_key("sub-title") or file1tagnames.has_key("sub-titleda"):
                f1prog.appendChild(titleDaNode)
            else:
                titleDaNode.tagName="sub-title"
                f1prog.appendChild(titleDaNode)
        
from codecs import open
outfile = open(sys.argv[2], "w", "utf-8")
outfile.write(file1.toxml())
outfile.close()
