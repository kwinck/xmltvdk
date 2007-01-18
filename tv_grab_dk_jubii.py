#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from urllib import urlopen
import sys, time

def jumptime (days = 0, hours = 0, minutes = 0):
    t = [u for u in time.localtime()]
    t[3:9] = [0]*6
    t = time.mktime(t) + days*24*60*60 + hours*60*60 + minutes*60
    t += time.mktime(time.localtime()) - time.mktime(time.gmtime(time.time()))
    return time.gmtime(t)

retries = 3
def readUrl (url):
    for i in range (retries):
        try:
            data = urlopen(url).read()
            if data.find("<title>Jubii - 404</title>") >= 0:
                continue
            return data
        except: pass
    return None

days = 6
gurl = "http://tv.jubii.dk/tvflash.ashx?startdato=%s&slutdato=%s&channelgroup=%s"
today = time.strftime("%d-%m-%Y",jumptime(1))
endday = time.strftime("%d-%m-%Y",jumptime(days))

sys.stderr.write("Henter kanal- og udsendelsesinformation...\n")
pagedata = ""
#Kunne optimeres en del, ved ikke at hente udenlandske, hvor de ikke er nødvendige
for page in "danske", "udenlandske":
    pagedays = days
    while True:
        data = readUrl(gurl % (today, endday, page))
        if data or pagedays == 1: break
        pagedays -= 1
        endday = time.strftime("%d-%m-%Y",jumptime(pagedays))
    if not data:
        sys.stderr.write("Ingen data for %s \n" % page)
        continue
    pagedata += data[:data.find("</tv>")]
pagedata += "</tv>"

dontparse = False
#if not pagedata or pagedata.find("<title>Jubii - 404</title>") >= 0:
#    sys.stderr.write("Kunne ikke hente kanal- og udsendelsesinformation. Skriver tom fil.\n")
#    dontparse = True

from sgmllib import SGMLParser
class ChannelGrabber(SGMLParser):
    def __init__(self, text, channels=[]):
        SGMLParser.__init__(self)
        self.channels = channels
        if channels:
            self.programmes = {}
            for c in channels:
                self.programmes[c] = []
        
        if dontparse: return
        
        self.wassat = channels or None
        sys.stderr.write("Parser kanal- og udsendelsesinformation...\n")
        self.feed(text)

    def start_kanal(self, attrs):
        if not self.wassat:
            self.channels.append([v for k,v in attrs if k == "station"][0])
    
    def start_udsendelse(self, attrs):
        if self.wassat:
            for k, v in attrs:
                if k == "station":
                    #sys.stderr.write(str([v]))
                    if self.programmes.has_key(v):
                        self.programmes[v].append(self.toDic(attrs))
                    break
                    
    def toDic(self, tupples):
        dic = {}
        for k, v in tupples:
            dic[k] = v
        return dic

# ---------- Spørg til konfigurationsfil ---------- #

import os
from codecs import open
xmltvFolder = os.path.expanduser("~/.xmltv")
configureFile = os.path.expanduser("~/.xmltv/tv_grab_dk_jubii.conf")

if len(sys.argv) > 1 and sys.argv[1] == "--configure":
    cg = ChannelGrabber (pagedata)
    channels = map(lambda x: x.decode("iso-8859-1").encode("utf-8"), cg.channels)

    if not os.path.exists(xmltvFolder):
        os.mkdir(xmltvFolder)
    if os.path.exists(configureFile):
        answer = raw_input("Konfigurationsfilen eksisterer allerede. Vil du overskrive den? (y/N) ").strip()
        if answer != "y":
            sys.exit()
    file = open(configureFile, "w", "utf-8")
    for name in channels:
        answer = raw_input("Tilføj %s (y/N) " % name).strip()
        if answer == "y":
            file.write("%s\n" % name.decode("utf-8"))
        else: file.write("#%s\n" % name.decode("utf-8"))
    sys.exit()

elif not os.path.exists(configureFile):
    print "Kan ikke finde configfile: %s" % configureFile
    sys.exit()

# ---------- Læs fra konfigurationsfil ---------- #

chosenChannels = []
for line in open(configureFile, "r", "utf-8"):
    line = line.strip()
    if not line.startswith("#"):
        chosenChannels.append(line.encode("utf-8"))

cg = ChannelGrabber (pagedata, chosenChannels)
chosenProgrammes = cg.programmes

# ---------- Klasser til parsing ---------- #

def iteratelists(*lists):
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

def splitPersons (persons):
    persons = persons.split(", ")
    loc = persons[-1].find(" og ")
    if loc >= 0:
        persons.append(persons[-1][loc+4:])
        persons[-2] =persons[-2][:loc]
    return persons

def splitTitle (title):
    t = [title, ""]
    
    if title.find(":") >= 0:
        splited = title.split(":",1)
        t[0] = splited[0]
        t[1] = splited[1].strip()
    
    elif title.find(" - ") >= 0:
        splited = title.split(" - ",1)
        t[0] = splited[0]
        t[1] = splited[1]
    
    return t

def isSubtitle (text):
    text = text.strip()
    return len(text.split()) <= 5 and \
           text[:-1].find(".") < 0

def parseSubtitle (subtitle, dic):
    subtitle = subtitle.strip()
    if subtitle.endswith("."):
        subtitle = subtitle[:-1]
    s = subtitle.rfind("(")
    if s > -1:
        e = subtitle.find(")",s)
        no = [s.strip() for s in subtitle[s+1:e].split(":")]
        if no[0].isdigit():
            if len(no) >= 2 and no[1].isdigit():
                dic["episode"] = "..%s/%s" % (no[0],no[1])
            else: dic["episode"] = "..%s" % no[0]
            dic["sub-titleda"] = subtitle[:e+1]
            # Ret til subtitle[:s], hvis du ikke vil have at (1) bliver i subtitlen.
    else:
        dic["sub-titleda"] = subtitle

def parseTime (time):
    return time.replace("-","").replace(":","").replace("T","").encode("utf-8")

iso = lambda x: x
actorDir = {"Kommentator":"commentator", "Medvirkende":"actor",
iso("Redaktør"):"producer", iso("Tilrettelæggelse"):"producer",
iso("Vært"):"presenter", iso("Studievært"):"presenter"}

import re
ampPattern = re.compile("&(?!amp;)")

def parseProgramme (programme):
    programmeDic = {}
    
    programmeDic["start"] = parseTime(programme["startdato"])
    programmeDic["slut"] = parseTime(programme["slutdato"])
    programmeDic["kanal"] = programme["station"]
    
    title, subtitle = splitTitle(programme["titel"].replace("& ","&amp; "))
    programmeDic["titleda"] = title
    if subtitle: parseSubtitle(subtitle,programmeDic)
    
    programmeDic["categoryda"] = programme["kategori"].replace("& ","&amp; ")
    
    if "--nodesc" in sys.argv:
        return programmeDic
    
    url = "http://tv.jubii.dk/Program.aspx?id=%s" % programme["id"]
    data = readUrl(url)
    
    if not data:
        return programmeDic
    
    start = data.find("<span id=\"ProgramText\">")+23
    end = data.find("</span>", start)
    desc = data[start:end]
    desc = ampPattern.sub("&amp;", desc)
    desc = desc.decode("iso-8859-1").encode("utf-8")
    
    if not desc == "Ingen beskrivelse.":
        for line in desc.split("<BR>"):
            con = False
            for k, v in actorDir.iteritems():
                if line.startswith(k):
                    s = line.find(":")+2
                    if line[-1] == ".": line = line[s:-1]
                    programmeDic[v] = splitPersons(line)
                    con = True
                    break
            if con: continue
    
            if not programmeDic.has_key("descda"):
                programmeDic["descda"] = line
            elif not programmeDic.has_key("sub-titleda") and \
                    len(line) > len(programmeDic["descda"]) and \
                    isSubtitle(programmeDic["descda"]):
                parseSubtitle(programmeDic["descda"],programmeDic)
                programmeDic["descda"] = line
            else: programmeDic["descda"] += "\n%s" % line
    
    if not "sub-titleda" in programmeDic and \
            "descda" in programmeDic and \
            len(programmeDic["descda"].split()) <= 4 and \
            programmeDic["descda"].strip()[:-1].find(".") < 0:
        parseSubtitle(programmeDic["descda"], programmeDic)
        del programmeDic["descda"]
    
    return programmeDic

# ---------- Parse ---------- #

keyDic = {"titleda":"title lang=\"da\"", "sub-titleda":"sub-title lang=\"da\"",
"categoryda":"category lang=\"da\"", "descda":"desc lang=\"da\"", "episode":"episode-num system=\"xmltv_ns\""}

credits = ("director", "actor", "writer", "adapter", "producer",
                   "presenter", "commentator", "guest")

sqaresPerProgramme = 10

sys.stderr.write("Parser: ")
print u"<?xml version=\"1.0\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

for channel in chosenProgrammes.keys():
    sys.stderr.write("\n%s: "%channel)

    print "<channel id=\"%s\"><display-name>%s</display-name></channel>" % \
        (channel, ampPattern.sub("&amp;", channel))
    
    if len(chosenProgrammes[channel]) <= 0:
        continue
    
    print len(chosenProgrammes[channel])
    squareVar = len(chosenProgrammes[channel]) / sqaresPerProgramme
    for programme, i in iteratelists(chosenProgrammes[channel],
                                     xrange(len(chosenProgrammes[channel]))):
        
        if squareVar < 0 and i % squareVar == 0 and i != 0:
            sys.stderr.write("#")

        if i+1 < len(chosenProgrammes[channel]):
            if programme["startdato"] == chosenProgrammes[channel][i+1]["startdato"]:
                if "--debug" in sys.argv:
                    sys.stderr.write("Skipper %s (%s) til fordel for %s (%s)\n" % \
                            (programme["titel"], programme["startdato"], \
                            chosenProgrammes[channel][i+1]["titel"], \
                            chosenProgrammes[channel][i+1]["startdato"]))
                continue
            if int(parseTime(programme["slutdato"])) > \
                    int(parseTime(chosenProgrammes[channel][i+1]["startdato"])):
                programme["slutdato"] = chosenProgrammes[channel][i+1]["startdato"]
        
        pDic = parseProgramme(programme)
        
        print "<programme channel=\"%s\" start=\"%s\" stop=\"%s\">" % \
            (pDic["kanal"], pDic["start"], pDic["slut"])
    
        for key, value in keyDic.iteritems():
            if pDic.has_key(key):
                print "<%s>%s</%s>" % (keyDic[key], \
                                pDic[key], \
                                keyDic[key].split(" ")[0])
        
        if len([c for c in credits if c in programme]) > 0:
            print "<credits>"
            for c in credits:
                if pDic.has_key(c):
                    for credit in pDic[c]:
                        print "<%s>%s</%s>" % (c,credit,c)
            print "</credits>"
    
        print "</programme>"
    
print "</tv>"
sys.stderr.write("\nFærdig...\n")
