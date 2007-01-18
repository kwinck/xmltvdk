#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from urllib import urlopen, urlencode
from sgmllib import SGMLParser

# ---------- Lav kanal liste ---------- #

def createChannelList ():
    front = urlopen("http://www.ahot.dk/tv/").read()
    start = front.find("<SELECT id=cboKanal")
    end = front.find("</SELECT>", start+len("<SELECT id=cboKanal"))
    channels = front[start:end+len("</SELECT>")]
    
    class ChannelGrabber(SGMLParser):
        def __init__(self, text):
            SGMLParser.__init__(self)
            self.channels = []
            self.inOption = False
            self.feed(text)
    
        def start_option(self, attrs):
            for k, v in attrs:
                if k == "value":
                    return
            self.inOption = True
    
        def end_option(self):
            self.inOption = False
            
        def handle_data(self, text):
            if self.inOption:
                self.channels.append(text)
    
    cg = ChannelGrabber(channels)
    channels = cg.channels
    
    # Joiner programmer, der er blevet splittet op på grund af "&"
    
    i = 0
    while i < len(channels):
        if channels[i] == "&":
            channels[i-1] = "".join(channels[i-1:i+2])
            del channels[i]
            del channels[i]
        i += 1
    
    return channels
    
# ---------- Spørg til konfigurationsfil ---------- #

import os, sys
xmltvFolder = os.path.expanduser("~/.xmltv")
configureFile = os.path.expanduser("~/.xmltv/tv_grab_dk_ahot.conf")

if len(sys.argv) > 1 and sys.argv[1] == "--configure":
    channels = createChannelList()
    if not os.path.exists(xmltvFolder):
        os.mkdir(xmltvFolder)
    if os.path.exists(configureFile):
        answer = raw_input("Konfigurationsfilen eksisterer allerede. Vil du overskrive den? (y/N) ").strip()
        if answer != "y":
            sys.exit()
    file = open(configureFile, "w")
    for name in channels:
        answer = raw_input("Tilføj %s (y/N) " % unicode(name, "iso-8859-1").encode("utf-8")).strip()
        if answer == "y":
            file.write("%s\n" % name)
        else: file.write("#%s\n" % name)
    sys.exit()

elif not os.path.exists(configureFile):
    print "Kan ikke finde configfile: %s" % configureFile
    sys.exit()

# ---------- Læs fra konfigurationsfil ---------- #

chosenChannels = []
for line in open(configureFile):
    line = line.strip()
    if not line.startswith("#"):
        chosenChannels.append(line)

# ---------- Klasser til parsing ---------- #

import time
def parseTime (clock, date, midnight = 0):
    if clock == "":
        return ""
    ds = date.split("-")
    cs = clock.split(":")
    ds = map(int, ds)
    cs = map(int, cs)
    tt = (ds[2], ds[1], ds[0], cs[0], cs[1], 0, 1, 1, 0)
    if midnight:
	time32 = time.mktime(tt) - time.timezone
	tt = time.gmtime(time32 + 3600 * 24)
    iso_time = time.strftime("%Y%m%d%H%M%S", tt)
    return iso_time

def splitPersons (persons):
    persons = persons.split(", ")
    loc = persons[-1].find(" og ")
    if loc >= 0:
        persons.append(persons[-1][loc+4:])
        persons[-2] =persons[-2][:loc]
    return persons

def parseEpisode (episode):
    splitted = episode.split(":")
    e = int(splitted[0])-1
    if len(splitted) >= 2:
        ec = int(splitted[1])-1
    else: ec = 0
    return".%d/%d." % (e,ec)

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

import htmlentitydefs, re
k = map(len,htmlentitydefs.entitydefs.keys())
ampexpr = re.compile("&(?![a-zA-Z0-9]{%d,%d};)" % (min(k),max(k)))

class PageParser(SGMLParser):
    def __init__(self, text):
        SGMLParser.__init__(self)
        self.pieces = []
        self.date = ""
        self.lookingForDate = False
        self.lookingForTimeTitle = False
        start = text.find("<table width=\"100%\">")
        end = text.find("</table>", start+len("<table width=\"100%\">"))
        text = text[start:end+len("</table>")]
        text = ampexpr.sub("&amp;",text)
        self.feed(text)

    def start_tr(self, attrs):
        self.pieces.append({})
        self.tdNo = -1
    
    def start_td(self, attrs):
        for k, v in attrs:
            if k == "colspan" and v == "2":
                self.lookingForDate = True
                return
        self.tdNo += 1
    
    def end_td(self):
        self.lookingForDate = False
        
    def handle_data(self, text):
        #text = text.strip()
        if self.lookingForDate:
            self.date = text
        elif self.lookingForTimeTitle:
            if self.tdNo == 0:
                self.pieces[-1]["start"] = parseTime(text, self.date)
                if len(self.pieces) >= 2 and self.pieces[-2].has_key("start") and \
                        self.pieces[-2]["start"] == self.pieces[-1]["start"]:
                    del self.pieces[-2]
            elif self.tdNo == 1:
                title, subtitle = splitTitle(text)
                
                if self.pieces[-1].has_key("titleda"):
                    self.pieces[-1]["titleda"] += title
                else: self.pieces[-1]["titleda"] = title
                
                if subtitle and not self.pieces[-1].has_key("sub-titleda"):
                    self.pieces[-1]["sub-titleda"] = subtitle
    
    def start_font(self, attrs):
        self.lookingForTimeTitle = True
    def start_b(self, attrs):
        self.lookingForTimeTitle = True
    def end_font(self):
        self.lookingForTimeTitle = False
    def end_b(self,):
        self.lookingForTimeTitle = False
    def end_a(self):
        self.lookingForTimeTitle = False
    
    def start_a(self, attrs):
        self.lookingForTimeTitle = True
    
        v = [v for k,v in attrs if k == "href"][0]
        
        start = v.find("ID=")
        end = v.find("')", start+len("ID="))
        id = v[start+len("ID=") : end]
        data = urlopen("http://www.ahot.dk/tv/visprogram.asp?ID=%s" % id).read()
        
        start = data.find("<td width=\"100%\">\r\n")
        end = data.find("</td>", start+len("<td width=\"100%\">\r\n"))
        self.parseInfo(data[start+len("<td width=\"100%\">\r\n") : end])
    
    def parseInfo (self, info):
        info = info.replace("\r","")
        info = info.replace("<P>","\n")
        info = info.replace("<p>","\n")
        info = info.replace("<BR>","\n")
        info = info.replace("<br>","\n")
        info = info.replace("&nbsp;"," ")
        info = info.replace("<MEDVIRK>","") #Kan muligvis bruges til noget smart engang...
        info = info.strip()
        
        for line in info.split("\n"):
            line = line.strip()
            if line == "": continue
            loc = line.find("kl.")
            iso = lambda x: x.decode("utf-8").encode("iso-8859-1")
            if loc >= 0 and not self.pieces[-1].has_key("stop"):
                if line[loc+4:loc+5] > line[loc+12:loc+13]:
		    self.pieces[-1]["stop"] = parseTime(line[loc+12:loc+17], self.date, 1)
		else:
		    self.pieces[-1]["stop"] = parseTime(line[loc+12:loc+17], self.date, 0)
                
            elif line.startswith("Kategori:"):
                loc = line.find(" (")
                if loc >= 0:
                    self.pieces[-1]["category"] = line[10:loc]
                else: self.pieces[-1]["category"] = line[10:]
                
            elif line.startswith("\"") and (line.endswith("\"")
                    or line.endswith("\".")):
                self.pieces[-1]["sub-titleda"] = line[1:-2]
                
            elif line.startswith("Kommentator"):
                self.pieces[-1]["commentator"] = \
                    splitPersons(line[line.find(":")+2 : max(line.find("Send")-2,-1)])
            elif line.startswith("Medvirkende"):
                self.pieces[-1]["actor"] = \
                    splitPersons(line[line.find(":")+2 : max(line.find("Send")-2,-1)])
            elif line.startswith(iso("Redaktør")) or \
                    line.startswith(iso("Tilrettelæggelse")):
                self.pieces[-1]["producer"] = \
                    splitPersons(line[line.find(":")+2 : max(line.find("Send")-2,-1)])
            elif line.startswith(iso("Vært")) or line.startswith(iso("Studievært")):
                self.pieces[-1]["presenter"] = \
                    splitPersons(line[line.find(":")+2 : max(line.find("Send")-2,-1)])
            
            elif line.startswith("Originaltitel"):
                title = line[15:]
                title, subtitle = splitTitle(title)
                
                if self.pieces[-1].has_key("title"):
                    self.pieces[-1]["title"] += title
                else: self.pieces[-1]["title"] = title
                
                if subtitle and not self.pieces[-1].has_key("sub-title"):
                    self.pieces[-1]["sub-title"] = subtitle

            elif line.startswith("Episode"):
                self.pieces[-1]["episode"] = \
                    parseEpisode(line[line.find("(")+1:-1])
                    
            else:
                if line.split(" ") <= 3 and \
                        not self.pieces[-1].has_key("sub-titleda"):
                    self.pieces[-1]["sub-titleda"] = line
                
                elif self.pieces[-1].has_key("desc"):
                    self.pieces[-1]["desc"] += "\n%s" % line
                else: self.pieces[-1]["desc"] = line

# ---------- Parse ---------- #
sys.stderr.write("Parsing...\n")

keyDic = {"title":"title", "sub-title":"sub-title", "titleda":"title lang=\"da\"",
"sub-titleda":"sub-title lang=\"da\"", "category":"category lang=\"da\"",
"desc":"desc lang=\"da\"", "episode":"episode-num system=\"xmltv_ns\""}

credits = ("director", "actor", "writer", "adapter", "producer",
                   "presenter", "commentator", "guest")

print "<?xml version=\"1.0\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print "<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

def fix (text):
	text = unicode(text, "iso-8859-1").encode("utf-8")
	text = text.replace("&","&amp;")
	return text

for channel in chosenChannels:
    channeliso = channel
    channel = fix(channel)
    sys.stderr.write("%s...\n" % channel)

    data = urlopen("http://www.ahot.dk/tv/soeg.asp",
        urlencode({"cboDato":"xx", "cboKanal":channeliso})).read()

    pp = PageParser(data)
    programmes = pp.pieces
    
    print "<channel id=\"%s\"><display-name>%s</display-name></channel>" % (channel, channel)
    
    for programme in programmes:
        if not "start" in programme:
            continue
    
        if not "stop" in programme:
            print "<programme channel=\"%s\" start=\"%s\">" % \
                (channel, programme["start"])
        else:
            print "<programme channel=\"%s\" start=\"%s\" stop=\"%s\">" % \
                (channel, programme["start"], programme["stop"])
        
        for key, value in keyDic.iteritems():
            if programme.has_key(key):
                print "<%s>%s</%s>" % (keyDic[key], fix(programme[key]), keyDic[key].split(" ",1)[0])
        
        if len([c for c in credits if c in programme]) > 0:
            print "<credits>"
            for c in credits:
                if programme.has_key(c):
                    for credit in programme[c]:
                        print "<%s>%s</%s>" % (c,fix(credit),c)
            print "</credits>"

        print "</programme>"
    
print "</tv>"

sys.stderr.write("\nFærdig...\n")
