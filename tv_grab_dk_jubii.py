#!/usr/bin/env python
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
ampPattern = re.compile("&(?!amp;)")

# ---------- Kig på evt. kommandolinieargumenter ---------- #
grabbername = os.path.basename(sys.argv[0]).rstrip(".py")
xmlcdir = os.path.expanduser("~/.xmltv/")
defaultconffile = os.path.normpath(os.path.join(xmlcdir,grabbername + ".conf"))

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

    parser.add_option("--nodesc", dest="desc", action="store_false",
                      default=True,
                      help="Do not grab descriptions (this is a lot faster).")
    parser.add_option("--debug", dest="debug", action="store_true",
                      default=False,
                      help="Show extra debug information.")


    options, args = parser.parse_args()

    if args:
        parser.error("Unknown argument(s): " + ", ".join(map(repr, args)))

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

# ----------  ---------- #


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
            if data.find(">Jubii - 404</title>") >= 0:
                log("jubii-http-problem: 404-error. Retrying...\n")
                continue
            if data.find(">Runtime Error</title>") >= 0:
                log("jubii-http-problem: Runtime-error. Retrying...\n")
                continue
            return data
        except: pass
    return None

days = 6
gurl = "http://tv.jubii.dk/tvflash.ashx?startdato=%s&slutdato=%s&channelgroup=%s"
today = time.strftime("%d-%m-%Y",jumptime(1))
endday = time.strftime("%d-%m-%Y",jumptime(days))

log("Fetching channel and program information...\n")
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
        log("Ingen data for %s \n" % page)
        continue
    pagedata += data[:data.find("</tv>")]
pagedata += "</tv>"

dontparse = False
#if not pagedata or pagedata.find("<title>Jubii - 404</title>") >= 0:
#    log("Kunne ikke hente kanal- og udsendelsesinformation. Skriver tom fil.\n")
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
        log("Parsing channel and programinformation...\n")
        self.feed(text)

    def start_kanal(self, attrs):
        if not self.wassat:
            self.channels.append([v for k,v in attrs if k == "station"][0])
    
    def start_udsendelse(self, attrs):
        if self.wassat:
            for k, v in attrs:
                if k == "station":
                    #log(str([v]))
                    if self.programmes.has_key(v):
                        self.programmes[v].append(self.toDic(attrs))
                    break
                    
    def toDic(self, tupples):
        dic = {}
        for k, v in tupples:
            dic[k] = v
        return dic

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

    cg = ChannelGrabber (pagedata)
    channels = map(lambda x: x.decode("utf-8"), cg.channels)

    file = codecs.open(configureFile, "w", "utf-8")
    for name in channels:
        answer = raw_input(u"Add channel %s (y/N) " % name)
        if answer.strip().startswith("y"):
            file.write("%s\n" % name)
        else:
            file.write("#%s\n" % name)
    sys.exit()

elif not os.path.isfile(configureFile) and not options.listchannels:
    print u"Cannot open configurefile '%s' for input: %s." % (
        options.configfile, e.strerror)
    print u"Use --configure to configure the grabber."
    sys.exit(1)

# ---------- Skift output, hvis ønsket ---------- #

# ALSO after this point we only output XML - ensure that we can do
# utf-8 output for the XMl

if options.output != "-":
    try:
        sys.stdout = codecs.open(options.output, "w","utf-8")
    except IOError, e:
        print u"Cannot open '%s' for output: %s" % (options.output, e.strerror)
        sys.exit(1)
else:
    # Force utf-8 on output (otherwise we may get a UnicodeEncodeError
    # when doing redirects, i.e., tv_grab_dk_ontv ... > filename)
    sys.stdout = codecs.getwriter('UTF-8')(sys.stdout)


# ---------- Lav --list-channels ---------- #

if options.listchannels:
    cg = ChannelGrabber (pagedata)
    channels = map(lambda x: x.decode("utf-8"), cg.channels)

    print u'<?xml version="1.0" encoding="UTF-8"?>'
    print u"<!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
    print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"
    
    for channel in channels:
        print u"<channel id=\"%s\">" % channel
        print u"    <display-name>%s</display-name>" % ampPattern.sub("&amp;", channel)
        print u"</channel>"

    print u"</tv>"
    sys.exit(0)

# ---------- Læs fra konfigurationsfil ---------- #

chosenChannels = []
for line in codecs.open(configureFile, "r","iso-8859-1"):
    line = line.strip()
    if not line.startswith("#"):
        chosenChannels.append(line.encode("utf-8"))

cg = ChannelGrabber (pagedata, chosenChannels)
chosenProgrammes = cg.programmes

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

def parseTime (time):
    return addTimeZone(time.replace("-","").replace(":","").replace("T",""))

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

actorDir = {
    u"Kommentator" : "commentator", 
    u"Medvirkende" : "actor",
    u"Redaktør" : "producer", 
    u"Tilrettelæggelse" : "producer",
    u"Vært" : "presenter",
    u"Studievært" : "presenter",
}

def parseProgramme (programme):
    global options
    programmeDic = {}
    
    programmeDic["start"] = parseTime(programme["startdato"])
    programmeDic["slut"] = parseTime(programme["slutdato"])
    programmeDic["kanal"] = programme["station"]
    
    title, subtitle = splitTitle(programme["titel"].replace("& ","&amp; ").decode("utf-8"))
    programmeDic["titleda"] = title
    if subtitle: parseSubtitle(subtitle,programmeDic)
    
    programmeDic["categoryda"] = programme["kategori"].replace("& ","&amp; ").decode("utf-8")
    
    if not options.desc:
        return programmeDic
    
    url = "http://tv.jubii.dk/Program.aspx?id=%s" % programme["id"]
    data = readUrl(url).decode("iso-8859-1")
    
    if not data:
        return programmeDic
    
    start = data.find("<span id=\"ProgramText\">")+23
    end = data.find("</span>", start)
    desc = data[start:end]
    desc = ampPattern.sub("&amp;", desc)
    
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
    
    start = data.find("<span id=\"ProgramShowView\">")+27
    end = data.find("</span>", start)
    programmeDic["showview"] = data[start:end]

    return programmeDic

# ---------- Parse ---------- #

keyDic = {"titleda":"title lang=\"da\"", "sub-titleda":"sub-title lang=\"da\"",
"categoryda":"category lang=\"da\"", "descda":"desc lang=\"da\"", "episode":"episode-num system=\"xmltv_ns\""}

credits = ("director", "actor", "writer", "adapter", "producer",
                   "presenter", "commentator", "guest")

sqaresPerProgramme = 10

log("Parser: ")
print u"<?xml version=\"1.0\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

for channel in chosenProgrammes.keys():
    channel = channel.decode("utf-8")
    print u"<channel id=\"%s\">" % channel
    print u"    <display-name>%s</display-name>" % ampPattern.sub("&amp;", channel)
    print u"</channel>"

for channel in chosenProgrammes.keys():
    # channel = channel.decode("utf-8")
    log(u"\n%s: " % repr(channel))

    if len(chosenProgrammes[channel]) <= 0:
        continue
    
    squareVar = len(chosenProgrammes[channel]) / sqaresPerProgramme
    for programme, i in iteratelists(chosenProgrammes[channel],
                                     xrange(len(chosenProgrammes[channel]))):
        
        if squareVar < 0 and i % squareVar == 0 and i != 0:
            log("#")

        if i+1 < len(chosenProgrammes[channel]):
            if programme["startdato"] == chosenProgrammes[channel][i+1]["startdato"]:
                if options.debug:
                    log(u"Skipper %s (%s) til fordel for %s (%s)\n" % 
                        (programme["titel"], programme["startdato"], 
                         chosenProgrammes[channel][i+1]["titel"], 
                         chosenProgrammes[channel][i+1]["startdato"]))
                continue
            if parseTime(programme["slutdato"]) > \
                    parseTime(chosenProgrammes[channel][i+1]["startdato"]):
                programme["slutdato"] = chosenProgrammes[channel][i+1]["startdato"]
        
        pDic = parseProgramme(programme)
        
        print u"<programme channel=\"%s\" start=\"%s\" stop=\"%s\" showview=\"%s\">" % \
            (pDic["kanal"].decode("utf-8"), pDic["start"], pDic["slut"], pDic["showview"])
    
        for key, value in keyDic.iteritems():
            if pDic.has_key(key):
                print u"<%s>%s</%s>" % (value,
                                        pDic[key],
                                        value.split(" ")[0])
        
        if len([c for c in credits if c in programme]) > 0:
            print u"<credits>"
            for c in credits:
                if pDic.has_key(c):
                    for credit in pDic[c]:
                        print u"<%s>%s</%s>" % (c,credit,c)
            print u"</credits>"
    
        print u"</programme>"
    
print u"</tv>"
log(u"\nDone...\n")
