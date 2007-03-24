#!/usr/bin/python
# -*- coding: UTF-8 -*-

# ---------- Lav kanal liste ---------- #
import sys
sys.stderr.write("Henter kanalliste...\n")

import urllib2
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor)
opener.open("http://www.tv-guiden.dk/Index/TVGuidenIndex.cfm") #Henter cookies

s = opener.open("http://www.tv-guiden.dk/Navigation/DenLangeTopBar.cfm").read()

loc = s.find("<SELECT NAME=\"Dag\"")
s = s[:loc]

from sgmllib import SGMLParser
class InfoBarParser(SGMLParser):
    def __init__(self, text):
        SGMLParser.__init__(self)
        self.pieces = []
        self.metFirstOption = False
        self.feed(text)

    def start_option(self, attrs):
        self.metFirstOption = True
        self.pieces.append([])
        for k, v in attrs:
            if k == "value":
                self.pieces[-1].append(v)
                break

    def handle_data(self, text):
        if self.metFirstOption:
            self.pieces[-1].append(text)

ibp = InfoBarParser(s)

genreLoc = ibp.pieces.index(['Alle genrer'])

channels = ibp.pieces[:genreLoc]
channels= [[k[1:],v] for k, v in channels if k[:1] == "0"]
genres = ibp.pieces[genreLoc+1:]
genreDic = {}
for value, genre in genres:
    genreDic[value] = genre

# ---------- Spørg til konfigurationsfil ---------- #

import os
xmltvFolder = os.path.expanduser("~/.xmltv")
configureFile = os.path.expanduser("~/.xmltv/tv_grab_dk_tvguiden_py.conf")

if len(sys.argv) > 1 and sys.argv[1] == "--configure":
    if not os.path.exists(xmltvFolder):
        os.mkdir(xmltvFolder)
    if os.path.exists(configureFile):
        answer = raw_input("Konfigurationsfilen eksisterer allerede. Vil du overskrive den? (y/N) ").strip()
        if answer != "y":
            sys.exit()
    file = open(configureFile, "w")
    for id, name in channels:
        answer = raw_input("Tilføj %s (y/N) " % name).strip()
        if answer == "y":
            file.write("%s %s\n" % (id, name))
        else: file.write("#%s %s\n" % (id, name))
    sys.exit()

elif not os.path.exists(configureFile):
    print "Kan ikke finde configfile: %s" % configureFile
    sys.exit()

# ---------- Klasser til parsing ---------- #

import time
def parseTime (clock, day):
    clocksplit = clock.split(".")
    try:
        hour = int(clocksplit[0]) + 1
    except: sys.stderr.write("%s, %d"&(clock,day))
    min = int(clocksplit[1])
    
    tt = time.localtime()
    tl = [v for v in tt]
    for i in range(3,8): tl[i] = 0
    t = time.mktime(tl)
    
    t += day*24*60*60
    t += hour*60*60
    t += min*60
    
    t += time.mktime(time.localtime()) - time.mktime(time.gmtime(time.time()))
    
    tt = [i for i in time.gmtime(t)]
    tt[8] = time.localtime()[8]
    iso_time = time.strftime("%Y%m%d%H%M%S", tt)
    return iso_time

import re
datePattern = re.compile('fra \d{4}$')

class InfoBarParser(SGMLParser):
    def __init__(self, text):
        SGMLParser.__init__(self)
        self.pieces = []
        self.channelIcon = ""
        self.lookingForDesc = False
        self.lookingForTitle = False
        self.tdNo = -1
        
        text = text.replace("\r\n", "")
        text = text.replace("\n", "")
        text = text.replace("&nbsp;", " ")
        text = text.replace("&", "+")
        text = text.replace("’", "'") #Nogen folk bruger accent i steddet for appostrof
        text = text.replace("<BR>", "\n")
        text = text.decode("iso-8859-1").encode("utf-8")
        text = text.replace("&oslash;", "ø")
        text = text.replace("&aring;", "å")
        text = text.replace("&aelih;", "æ")

        self.feed(text)

    def start_tr(self, attrs):
        self.pieces.append({})
        self.tdNo = -1
    
    def start_td(self, attrs):
        self.tdNo += 1
    
    def start_img(self, attrs):
        for k, v in attrs:
            if k == "src" and self.channelIcon == "":
                self.channelIcon = v
            elif self.tdNo == 1 and k == "alt":
                self.pieces[-1]["category"] = v
    
    def start_font(self, attrs):
        if attrs == [('size', '2'), ('face', 'Arial'), ('color', 'BLUE')]:
            self.lookingForTitle = True
        elif attrs == [('size', '1'), ('face', 'Arial'), ('color', 'BLACK')]:
            self.lookingForDesc = True
    
    def end_font(self):
        self.lookingForDesc = False
        self.lookingForTitle = False
        
    def handle_data(self, text):
        text = text.strip()
        if self.tdNo == 1:
            self.pieces[-1]["time"] = text
        elif self.tdNo == 2:
            if self.lookingForTitle:
                text = text.replace("(R)", "")
                loc = text.find("("); loc2 = text.find(")")
                if loc >= 0: self.splittitle(text[:loc],"")
                else: self.splittitle(text,"")
                if loc >= 0 and loc2 > loc:
                    epi = text[loc+1:loc2].split(":")
                    try:
                        if len(epi) >= 2:
                            self.pieces[-1]["episodeCount"] = int(epi[1])
                        self.pieces[-1]["episode"] = int(epi[0])
                    except: return
            elif self.lookingForDesc:
                self.handle_desc(text)
        else: #self.tdNo == 3
            pass
    
    def splittitle(self, title, prefix):
        titles = [t.strip() for t in title.split(":",1)]
        self.pieces[-1][prefix+"title"] = titles[0]
        if len(titles) > 1: self.pieces[-1][prefix+"sub-title"] = titles[1]

    #Rykket ud for bedre overskuelighed
    def handle_desc(self, text):
        self.pieces[-1]["desc"] = ""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("("):
                self.splittitle(line[1:line.find(")")],"org")
            elif datePattern.search(line[:-1]):
                self.pieces[-1]["date"] = line[-5:-1]
            elif line == "Filmen vises i bredformat.":
                self.pieces[-1]["format"] = "16:9"
            elif line.startswith("Medvirkende:"):
                actors = line[13:-1]
                self.pieces[-1]["actors"] = [actors]
                if actors.find(", ") >= 0:
                    actors = actors.split(", ")
                    loc = actors[-1].find(" og ")
                    if loc >= 0:
                        actors.append(actors[-1][loc+4:])
                        actors[-2] =actors[-2][:loc]
                    self.pieces[-1]["actors"] = actors
            elif line.startswith("Instruktion:"):
                self.pieces[-1]["instructor"] = line[13:-1]
            else: self.pieces[-1]["desc"] += line+"\n"
        self.pieces[-1]["desc"] = self.pieces[-1]["desc"].strip()

# ---------- Parse ---------- #
print "<?xml version=\"1.0\" encoding=\"utf-8\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print "<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

chosenChannels = []
for line in open(configureFile):
    line = line.strip()
    if line.startswith("#"): continue
    chosenChannels.append(line.split(" ",1))

groundUrl = "http://www.tv-guiden.dk/Diverse/DenLangeopdater.cfm?"

sys.stderr.write("Starter...")

for channel, channelName in chosenChannels:
    sys.stderr.write("\n%s"%channelName.strip().ljust(10))
    curl = groundUrl + "Station=%s&Land=0&Omtale=0" % channel
    
    channelName = unicode(channelName, "iso-8859-1").encode("utf-8")
    
    for day in xrange(6): #Kunne i teorien starte fra -2, men hvem har brug for det?
        sys.stderr.write(" "+str(day))
    
        opener.open(groundUrl + "Station=%s&Land=0&Dato=%s&Omtale=1" % (channel, str(day)))
        data = opener.open("http://www.tv-guiden.dk/Data/DenLangeOversigt.cfm").read()
        
        ibp = InfoBarParser(data)
        programmes = ibp.pieces[3:] #De første er affald
        programmes = [p for p in programmes if p.has_key("time")]
        
        if day == 0:
            print "<channel id=\"%s\"><display-name>%s</display-name>" % (channel, channelName)
            print "<icon src=\"http://www.tv-guiden.dk%s\"/></channel>" % ibp.channelIcon
        
        for programme in programmes:
            print "<programme channel=\"%s\" start=\"%s\">" % (channel, parseTime(programme["time"], day))
            
            if programme.has_key("instructor") or programme.has_key("actors"):
                print "<credits>"
                if programme.has_key("instructor"):
                    print "<director>%s</director>" % programme["instructor"]
                if programme.has_key("actors"):
                    for actor in programme["actors"]:
                        print "<actor>%s</actor>" % actor
                print "</credits>"
            
            if programme.has_key("episode"):
                e = programme["episode"]-1
                if programme.has_key("episodeCount"):
                    ec = programme["episodeCount"]-1
                else: ec = 0
                print "<episode-num system=\"xmltv_ns\">.%d/%d.</episode-num>" % (ec,e)
                
            skiplist = ("time", "instructor", "actors", "episode", "episodeCount")
            for k, v in programme.iteritems():
                if k in ("orgtitle", "orgsub-title"):
                    print "<%s>%s</%s>" % (k[3:], v, k[3:])
                elif k == "format":
                    print "<video><aspect>%s</aspect></video>" % v
                elif k in ("desc", "title", "category", "sub-title"):
                    print "<%s lang=\"da\">%s</%s>" % (k,v,k)
                elif k in skiplist:
                    pass
                else: print "<%s>%s</%s>" % (k,v,k)
            print "</programme>"
            
print "</tv>"

sys.stderr.write("\nFærdig...\n")
