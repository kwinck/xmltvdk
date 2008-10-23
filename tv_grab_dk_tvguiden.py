#!/usr/bin/python
# -*- coding: utf-8 -*-
#
VERSION = "$Id$"

import codecs
import datetime
import locale
import optparse
import os
import sys
import time
from urllib import urlopen
import sys, time
import re

# ---------- Kig på evt. kommandolinieargumenter ---------- #
grabbername = os.path.basename(sys.argv[0]).rstrip(".py")
xmlcdir = os.path.expanduser("~/.xmltv/")
defaultconffile = os.path.normpath(os.path.join(xmlcdir,grabbername + ".conf"))
maxdays = 6

def parseOpts():
    global grabbername
    global defaultconffile
    global maxdays
    global cachepolicies, defaultcachepolicy, defaultcachedir

    parser = optparse.OptionParser()

    parser.usage = """
To show version:                %prog --version
To show capabilities:           %prog --capabilities
To list all available channels: %prog --list-channels [options]
To configure:                   %prog --configure [options]
To grab listings:               %prog [options]"""

    xopts = [
        ("version", "version", "Show the version of the grabber."),
        ("capabilities", "capabilities", "Show xmltv capabilities."),
        ("list-channels","listchannels","Output a list of all channels that data is "
         "available for. The list is in xmltv-format."),
        ("configure","configure","Prompt for which stations to download and "
         "write the configuration file."),
        ]
    for (opt, var, text) in xopts:
        parser.add_option("--"+opt, dest=var, action="store_true",
                          default=False, help=text)

    parser.add_option("--config-file", dest="configfile", metavar="FILE",
                      default=defaultconffile, help =
                      ("Set the name of the configuration file, the default "
                       "is %s. This is the file written by --configure "
                       "and read when grabbing." % defaultconffile))
    
    parser.add_option("--quiet", dest="verbose", action="store_false",
                      default=True,
                      help="Be quiet.")
    parser.add_option("--output", dest="output", metavar="FILENAME",
                      default="-",
                      help=("File name of output xml file. If not provided "
                            "or '-', stdout is used."))

    parser.add_option("--days", dest="days", metavar="N", default=maxdays,
                      type=int,
                      help="When grabbing, grab N days rather than %d."
                      % maxdays)
    parser.add_option("--offset", dest="offset", metavar="N", default=0,
                      type=int,
                      help="Start grabbing at today + N days, 0 <= N")
    
    parser.add_option("--nodesc", dest="desc", action="store_false",
                      default=True,
                      help="Do not grab descriptions (this is a lot faster).")
    parser.add_option("--debug", dest="debug", action="store_true",
                      default=False,
                      help="Show extra debug information.")


    options, args = parser.parse_args()

    if args:
        parser.error("Unknown argument(s): " + ", ".join(map(repr, args)))

    if options.days < 1:
        parser.error("--days should be at least 1")
    if options.days > maxdays:
        sys.stderr.write("--days can be at most %d. Using --days=%d\n" % 
                         (maxdays,maxdays))
        options.days = maxdays
    if options.offset < 0:
        parser.error("--offset should be at least 0")
    if options.offset >= maxdays:
        parser.error("--offset can be at most %d" % (maxdays-1))

    if len([x for _,x,_ in xopts if eval("options."+x)]) > 1:
        parser.error("You can use at most one of the options: " +
                     ", ".join(["--"+x for x,_ in xopts]))

    if options.version:
        global VERSION
        print VERSION
        print "For more information, see:"
        print "http://niels.dybdahl.dk/xmltvdk/index.php/Forside"
        sys.exit(0)
    if options.capabilities:
        print "baseline"
        print "manualconfig"
        sys.exit(0)

    return options
options = parseOpts()

# ensure that we can do Danish characters on stderr
sys.stderr = codecs.getwriter(locale.getpreferredencoding())(sys.stderr)

if options.verbose:
    log = sys.stderr.write
else:
    log = lambda x: x

# ---------- Lav kanal liste ---------- #
import sys
log("Fetching list of channels...\n")

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

configureFile = options.configfile
if options.configure:
    # ensure that we can do Danish characters
    sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)
    folder = os.path.dirname(configureFile)
    if not os.path.exists(folder):
        os.makedirs(folder)
    if os.path.exists(configureFile):
        answer = raw_input(u"'%s' does already exist. Do you want to overwrite it? (y/N) " % options.configfile).strip().lower()
        if answer.strip().lower() != "y":
            sys.exit()

    file = codecs.open(configureFile, "w", "utf-8")
    for cid, name in channels:
        cid = cid.decode("iso-8859-1")
        name = name.decode("iso-8859-1")
        answer = raw_input(u"Add channel %s (y/N) " % name)
        if not answer.strip().startswith("y"):
            file.write(u"# ")
        file.write(u"%s %s\n" % (cid, name))
    sys.exit()

elif not options.listchannels:
    # try to read the file
    try:
        try: 
            lines = codecs.open(options.configfile, "r", "utf-8").readlines()
        except UnicodeDecodeError:
            lines = codecs.open(options.configfile, "r", "iso-8859-1").readlines()
    except IOError, e:
        sys.stderr.write(u"Cannot open configurefile '%s' for input: %s.\n" % (
                options.configfile, e.strerror))
        sys.stderr.write(u"Use --configure to configure the grabber.\n")
        sys.exit(1)
        
    chosenChannels = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            chosenChannels.append(line.split(" ",1))        

# ---------- Skift output, hvis ønsket ---------- #

# ALSO after this point we only output XML - ensure that we can do
# utf-8 output for the XMl

if options.output != "-":
    try:
        sys.stdout = codecs.open(options.output, "w","utf-8")
    except IOError, e:
        sys.stderr.write(u"Cannot open '%s' for output: %s" % 
                         (options.output, e.strerror))
        sys.exit(1)
else:
    # Force utf-8 on output (otherwise we may get a UnicodeEncodeError
    # when doing redirects, i.e., tv_grab_dk_ontv ... > filename)
    sys.stdout = codecs.getwriter('UTF-8')(sys.stdout)

# ---------- Lav --list-channels ---------- #

if options.listchannels:

    print u'<?xml version="1.0" encoding="UTF-8"?>'
    print u"<!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
    print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

    for cid, name in channels:
        cid = cid.decode("iso-8859-1")
        name = name.decode("iso-8859-1")
        print u"<channel id=\"%s\">" % cid
        print u"    <display-name>%s</display-name>" % name
        # no icon since this would require us to read extra data
        print u"</channel>"

    print u"</tv>"
    sys.exit(0)

# ---------- Funktioner til at lave tidszoner korrekt ---------- #
# se evt. timefix.py

class LocalTimeZone(datetime.tzinfo):
    "Use timezone information according to the module time"
    def __init__(self, is_dst = -1):
        datetime.tzinfo.__init__(self)
        if is_dst == -1:
            self.is_dst = -1
        else:
            self.is_dst = int(bool(is_dst)) # ensure a 0 or 1 value

    def _dtOffset(self, dt):
        dtt = dt.replace(tzinfo = None).timetuple()[:-1] + (self.is_dst,)
        tst = time.localtime(time.mktime(dtt))
        return [-time.timezone, -time.altzone, None][tst[-1]]
    
    def utcoffset(self, dt):
        offset = self._dtOffset(dt)
        if offset is None: return None
        return datetime.timedelta(0,offset)
    
    def dst(self, dt):
        offset = self._dtOffset(dt)
        if offset is None: return None
        return datetime.timedelta(0,offset+time.timezone)
    
    def localize(self, dt, is_dst = -1):
        return dt.replace(tzinfo = LocalTimeZone(is_dst))

try:
    # see: http://pytz.sourceforge.net/
    import pytz
    mytz = pytz.timezone("Europe/Copenhagen")
except ImportError:
    mytz = LocalTimeZone()

def splitTimeStamp(ts):
    assert(len(ts) in [8,12,14])
    tss = [int(ts[i:i+2]) for i in range(2, len(ts),2)]
    tss[0] += int(ts[:2])*100

    return tuple(tss)

def addTimeZone(ts, is_dst = -1):
    global mytz

    tss = splitTimeStamp(ts)
    try:
        dt = datetime.datetime(*tss)
        ldt = mytz.localize(dt, is_dst)
        return ts + " " + ldt.strftime("%z")
    except IndexError:
        # is returned only for non-existing points in time, e.g.
        # at 2:30 when changing from winter to summer time.
        sys.stderr.write("Warning: Cannot find time zone for %s.\n" % repr(ts))
        return ts

# ---------- Klasser til parsing ---------- #

def noon(day):
    """Return time tuple curresponding to noon of day, 
    e.g. (2008,12,31,12,0,0,0,1,-1))"""
    now = time.localtime() 
    noon = time.mktime(now[:3] + (12,0,0,0,1,-1))
    if 0 <= now[3] <= 5: 
        day -= 1
    return time.localtime(noon + day * 24*3600)[:3] + (12,0,0,0,1,-1)

def parseTime (clock, day):
    """day is offset from today=0. clock is e.g. 01.40"""

    date = time.strftime("%Y%m%d", noon(day))
    res = date + clock.replace(".","")
    return addTimeZone(res)

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
        text = text.replace("’", "'") #Nogle folk bruger accent i stedet for apostrof
        text = text.replace("<BR>", "\n")
        text = text.decode("iso-8859-1")

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
print u"<?xml version=\"1.0\" encoding=\"utf-8\" ?>\n<!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

groundUrl = "http://www.tv-guiden.dk/Diverse/DenLangeopdater.cfm?"

log("Grabbing...")

for channel, channelName in chosenChannels:
    log("\n%s"%channelName.strip().ljust(10))
    curl = groundUrl + "Station=%s&Land=0&Omtale=0" % channel
    
    for day in xrange(options.offset, min(options.offset+options.days,maxdays)):
        log(" "+str(day))
    
        opener.open(groundUrl + "Station=%s&Land=0&Dato=%s&Omtale=1" % (channel, str(day)))
        data = opener.open("http://www.tv-guiden.dk/Data/DenLangeOversigt.cfm").read()
        
        ibp = InfoBarParser(data)
        programmes = ibp.pieces[3:] #De første er affald
        programmes = [p for p in programmes if p.has_key("time")]
        
        if day == 0:
            print u"<channel id=\"%s\">" % channel
            print u"    <display-name>%s</display-name>" % channelName
            print u"    <icon src=\"http://www.tv-guiden.dk%s\"/>" % ibp.channelIcon
            print u"</channel>"
            
        lastTime = ""
        for programme in programmes:
            start = programme["time"]
            if start < lastTime: # we are crossing midnight
                day +=1 
            lastTime = start
            start = parseTime(start, day)
            print u"<programme channel=\"%s\" start=\"%s\">" % (channel, start)
            
            if programme.has_key("instructor") or programme.has_key("actors"):
                print u"<credits>"
                if programme.has_key("instructor"):
                    print u"<director>%s</director>" % programme["instructor"]
                if programme.has_key("actors"):
                    for actor in programme["actors"]:
                        print u"<actor>%s</actor>" % actor
                print u"</credits>"
            
            if programme.has_key("episode"):
                e = programme["episode"]-1
                if programme.has_key("episodeCount"):
                    ec = programme["episodeCount"]
                    s = ".%d/%d." % (e,ec)
                else:
                    s = ".%d." % e
                print u"<episode-num system=\"xmltv_ns\">%s</episode-num>" % s
                
            skiplist = ("time", "instructor", "actors", "episode", "episodeCount")
            for k, v in programme.iteritems():
                if k in ("orgtitle", "orgsub-title"):
                    print u"<%s>%s</%s>" % (k[3:], v, k[3:])
                elif k == "format":
                    print u"<video><aspect>%s</aspect></video>" % v
                elif k in ("desc", "title", "category", "sub-title"):
                    print u"<%s lang=\"da\">%s</%s>" % (k,v,k)
                elif k in skiplist:
                    pass
                else: print u"<%s>%s</%s>" % (k,v,k)
            print u"</programme>"
            
print u"</tv>"

log("\nDone...!\n")
