#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# ---------- Read ---------- #

import sys
from xml.dom import minidom
dom = minidom.parse(sys.argv[1])

# read header
head = dom.getElementsByTagName("epg_data")[0]
feedLang = head.attributes["language"].value.encode("utf-8")

childsOf = lambda parent: [n for n in parent.childNodes if n.nodeType == n.ELEMENT_NODE]
# read Categories
categories = {}
parentID = 0
for node in childsOf(dom.getElementsByTagName("categories")[0]):
    categories[parentID] = node.attributes["value"].value
    childID = 0
    for cNode in childsOf(node):
        catID = (childID << ((1 * 8) & 0x1f)) | parentID
        categories[catID] = cNode.attributes["value"].value
        childID += 1;
    parentID += 1

ga = lambda n, k: n.attributes[k].value
# read Attributes
attributes = {}
attrID = 0
for node in childsOf(dom.getElementsByTagName("programAttributes")[0]):
    attributes[1 << attrID] = node.attributes["id"].value
    attrID += 1

# read RatingAttributes
ratingAttributes = []
attrID = 0
for node in childsOf(dom.getElementsByTagName("programRatingAttributes")[0]):
    ratingAttributes.append((1 << attrID, ga(node,"type"), ga(node,"value")))
    attrID += 1

# read scheduleAttributes
scheduleAttributes = []
attrID = 0
for node in childsOf(dom.getElementsByTagName("scheduleEntryAttributes")[0]):
    scheduleAttributes.append((1 << attrID, ga(node,"id")))
    attrID += 1

# read channels
channels = []
for s in dom.getElementsByTagName("s"):
    channels.append(s.attributes["name"].value)

# ---------- Spørg til konfigurationsfil ---------- #
import os
xmltvFolder = os.path.expanduser("~/.xmltv")
configureFile = os.path.expanduser("~/.xmltv/tv_grab_dk_mce.conf")

if len(sys.argv) > 2 and sys.argv[2] == "--configure":
    if not os.path.exists(xmltvFolder):
        os.mkdir(xmltvFolder)
    if os.path.exists(configureFile):
        answer = raw_input("Konfigurationsfilen eksisterer allerede. Vil du overskrive den? (y/N) ").strip()
        if answer != "y":
            sys.exit()
    file = open(configureFile, "w")
    for i in range(len(channels)):
        answer = raw_input("Tilføj %s (y/N) " % channels[i].encode("utf-8")).strip()
        if answer == "y":
            file.write("%s %s\n" % (i, channels[i].encode("utf-8")))
        else: file.write("#%s %s\n" % (i, channels[i].encode("utf-8")))
    sys.exit()

elif not os.path.exists(configureFile):
    sys.stderr.write("Kan ikke finde configfile: %s\n" % configureFile)
    sys.exit()

# ---------- Læs fra konfigurationsfil ---------- #

chosenChannels = []
for line in open(configureFile, "r"):
    line = line.strip()
    if not line[0] == "#":
        chosenChannels.append(line.split(" ",1)[0])

# ---------- ParseMethods ---------- #

# parse methods
def parseTime (stamp):
    g = [l for l in time.localtime()]
    g[-1] = 0
    stamp += time.mktime(g) - time.mktime(time.gmtime(time.time()))
    return time.strftime("%Y%m%d%H%M%S", time.gmtime(stamp))

def parsePAttr (attr, dic):
    pass #Underlige attributes, som xmltv ikke bruger

maxStars = 8
def parseRAttr (attr, dic):
    ratings = [(t,v) for k,t,v in ratingAttributes if attr & k]
    count = lambda s,c: len([d for d in s if d == c])
    for type, value in ratings:
        if type == "RATING_MOVIE":
            dic["rating:mpaa"] = value
        elif type == "RATING_STAR":
            sys.stderr.write("%s\n"%value)
            dic["stars"] = count(value,"*")*2
            if value.endswith("+"): dic["stars"] += 1
        elif type == "RATING_REASON":
            dic["rating:us"] = value

def parseSAttr (attr, dic):
    attrs = [i for k,i in scheduleAttributes if attr & k]
    for stereo in "Stereo", "Dolby", "Dolby Digital":
        if stereo in attrs:
            dic["stereo"] = stereo.lower()
    if "SAP" in attrs: dic["stereo"] = "stereo"
    for premiere in "Premiere", "Series Premiere", "Season Premiere":
        if premiere in attrs:
            dic["premiere"] = True
    for finale in "Finale", "Series Finale", "Season Finale":
        if finale in attrs:
            dic["last-chance"] = True
    if "Letterbox" in attrs:
        dic["aspect"] = "16:9"
    if "HDTV" in attrs:
        dic["quality"] = "HDTV"
    if "Teletext" in attrs or "Subtitled" in attrs:
        dic["subtitles"] = "teletext"

def parseCredits (type, value, dic):
    value = value.split("/")
    for mce, xmltv in ("s","actor"),("c","director"),("h","presenter"),("g","guest"):
        if mce == type:
            dic[xmltv] = value
            break

def parseProgramme (node, channel, start, stop, seAttr):
    dic = {"channel": channel}
       
    for old, new in ("e","sub-title"), ("y","date"), ("d","desc"), ("t","title"):
        if node.attributes.has_key(old):
            dic[new] = node.attributes[old].value
                
    for i in range(10):
        if node.attributes.has_key("c%d"%i):
            dic["category"] = categories[int(node.attributes["c%d"%i].value)]
            break
                
    dic["start"] = parseTime(start)
    dic["stop"] = parseTime(stop)

    for key, func in ("a", parsePAttr), ("rt", parseRAttr), ("r", parseRAttr):
        if node.attributes.has_key(key):
            func(int(node.attributes[key].value), dic)
    parseSAttr(int(seAttr), dic)
    
    if node.attributes.has_key("l"):
        dic["language"] = node.attributes["l"].value
    
    for x in [y for y in "c","s","h","g" if node.attributes.has_key(y)]:
        parseCredits(x,node.attributes[x].value, dic)
        
    #??? Hvad skal "od" bruges til?
    
    return dic

# read programmes
import time
def parseSchedule (channels = None):
    progs = dom.getElementsByTagName("p")
    for ses in dom.getElementsByTagName("ses"):
        channel = ses.attributes["io"].value
        if channels != None and not channel in channels:
            continue
        start = time.mktime(time.strptime(ses.attributes["start"].value, "%Y-%m-%dT%H:%M:%S"))
        for se in childsOf(ses):
            start += int(se.attributes["d"].value)
            inf = (channel, start-int(se.attributes["d"].value), start, se.attributes["a"].value)
            yield parseProgramme(progs[int(se.attributes["p"].value)], *inf)

# ---------- Parse ---------- #

keyDic = {"title":"<title lang=\"%s\">"%feedLang, "sub-title":"<sub-title lang=\"%s\">"%feedLang, "category":"<category lang=\"%s\">"%feedLang, "desc":"<desc lang=\"%s\">"%feedLang, "date":"<date>", "stars":"<star-rating><value>", "surround":"<audio><stereo>", "language":"<language>", "subtitles":"<subtitles type=\"", "rating:mpaa":"<rating system=\"MPAA\"><value>", "rating:us":"<rating system=\"US\"><value>"}

endDic = {"title":"</title>", "sub-title":"</sub-title>", "category":"</category>", "desc":"</desc>", "date":"</date>", "stars":"/%d</value></star-rating>" % maxStars, "surround":"</audio></stereo>", "language":"</language>", "subtitles":"\" />", "rating:mpaa":"</value></rating>", "rating:us":"</value></rating>"}

oneDic = ("premiere", "last-chance")

inners = (("video",("aspect","quality")),
("credits",("director","actor","presenter","guest")))

sys.stderr.write("Parser\n")
print u"<?xml version=\"1.0\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

for i in chosenChannels:
    print "<channel id=\"%s\"><display-name lang=\"%s\">%s</display-name></channel>" % \
            (i, feedLang, channels[int(i)].encode("utf-8"))

for programme in parseSchedule(chosenChannels):
    print "<programme channel=\"%s\" start=\"%s\" stop=\"%s\">" % \
            (programme["channel"], programme["start"], programme["stop"])
    
    for key in programme.keys():
        if type(programme[key]) == int: continue
        if type(programme[key]) == list:
            for i in range(len(programme[key])):
                programme[key][i] = programme[key][i].encode("utf-8").replace("&","&amp;")
        else: programme[key] = programme[key].encode("utf-8").replace("&","&amp;")
    
    for key, value in keyDic.iteritems():
        if programme.has_key(key):
            print "%s%s%s" % (keyDic[key], programme[key], endDic[key])
    
    for tag, subtags in inners:
        if len([s for s in subtags if s in programme]) <= 0:
            continue
        print "<%s>" % tag
        for s in subtags:
            if programme.has_key(s):
                for value in programme[s]:
                    print "<%s>%s</%s>" % (s,value,s)
        print "</%s>" % tag

    for k in oneDic:
        if k in programme:
            print "<%s />" % k

    print "</programme>"
    
print "</tv>"
