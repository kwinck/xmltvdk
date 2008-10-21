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
from urllib import urlopen, urlencode
from sgmllib import SGMLParser

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

# ensure that we can do Danish characters on stderr as well : 
sys.stderr = codecs.getwriter(locale.getpreferredencoding())(sys.stderr)

if options.verbose:
    log = sys.stderr.write
else:
    log = lambda x: x


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
    channels = createChannelList()
    file = open(configureFile, "w")
    for name in channels:
        uname = name.decode("iso-8859-1")
        answer = raw_input(u"Add channel %s (y/N) " % uname)
        if answer.strip().startswith("y"):
            file.write("%s\n" % name)
        else:
            file.write("#%s\n" % name)
    sys.exit(0)

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
    channelList = createChannelList()
    print u'<?xml version="1.0" encoding="UTF-8"?>'
    print u"<!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
    print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"
    
    for channeli in channelList:
        channelu = channeli.decode("iso-8859-1").replace("&","&amp;")
        print u"<channel id=\"%s\">" % channelu
        print u"    <display-name>%s</display-name>" % channelu
        print "</channel>"
    print u"</tv>"
    sys.exit(0)

# ---------- Læs fra konfigurationsfil ---------- #

chosenChannels = []
for line in open(configureFile):
    line = line.strip()
    if not line.startswith("#"):
        chosenChannels.append(line)

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

# ---------- Klasser til parsing ---------- #

def parseTime (clock, date, midnight = 0):
    # if midnight is true, add an extra day to date
    if clock == "":
        return ""
    ds = date.split("-")
    cs = clock.split(":")
    ds = map(int, ds)
    cs = map(int, cs)
    date = datetime.date(ds[2], ds[1], ds[0])
    if midnight:
        date = datetime.date.fromordinal(date.toordinal()+1)
    time = datetime.time(cs[0], cs[1], 0)
    dt = datetime.datetime.combine(date,time)
    dt = mytz.localize(dt)
    return dt.strftime("%Y%m%d%H%M%S %z")

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
log("Parsing...\n")

keyDic = {"title":"title", "sub-title":"sub-title", "titleda":"title lang=\"da\"",
"sub-titleda":"sub-title lang=\"da\"", "category":"category lang=\"da\"",
"desc":"desc lang=\"da\"", "episode":"episode-num system=\"xmltv_ns\""}

credits = ("director", "actor", "writer", "adapter", "producer",
                   "presenter", "commentator", "guest")

print "<?xml version=\"1.0\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print "<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

def fix (text):
    return text.decode("iso-8859-1").replace("&","&amp;")

for channel in chosenChannels:
    channeliso = channel
    channel = fix(channel)
    print u"<channel id=\"%s\"><display-name>%s</display-name></channel>" % (channel, channel)
    
for channel in chosenChannels:
    channeliso = channel
    channel = fix(channel)
    log("%s...\n" % channel)

    data = urlopen("http://www.ahot.dk/tv/soeg.asp",
        urlencode({"cboDato":"xx", "cboKanal":channeliso})).read()

    pp = PageParser(data)
    programmes = pp.pieces
    
    for programme in programmes:
        if not "start" in programme:
            continue
    
        if not "stop" in programme:
            print u"<programme channel=\"%s\" start=\"%s\">" % \
                (channel, programme["start"])
        else:
            print u"<programme channel=\"%s\" start=\"%s\" stop=\"%s\">" % \
                (channel, programme["start"], programme["stop"])
        
        for key, value in keyDic.iteritems():
            if programme.has_key(key):
                print u"<%s>%s</%s>" % (keyDic[key], fix(programme[key]), keyDic[key].split(" ",1)[0])
        
        if len([c for c in credits if c in programme]) > 0:
            print u"<credits>"
            for c in credits:
                if programme.has_key(c):
                    for credit in programme[c]:
                        print u"<%s>%s</%s>" % (c,fix(credit),c)
            print u"</credits>"

        print u"</programme>"
    
print u"</tv>"

log("\nDone...\n")
