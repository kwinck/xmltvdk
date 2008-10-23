#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
VERSION = "$Id$"

import codecs
import datetime
import gzip
import locale
import optparse
import os
import re
import socket
import stat
import sys
import time
import urllib
import urllib2
socket.setdefaulttimeout(10)

# ---------- Kig på evt. kommandolinieargumenter ---------- #
grabbername = os.path.basename(sys.argv[0]).rstrip(".py")
xmlcdir = os.path.expanduser("~/.xmltv/")
defaultconffile = os.path.normpath(os.path.join(xmlcdir,grabbername + ".conf"))
maxdays = 15
cachepolicies = ["never","smart","always"]
defaultcachepolicy = 1 
defaultcachedir  = os.path.normpath(os.path.join(xmlcdir, "cache-ontv/"))

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
    
    parser.add_option("--cache", dest="cachedir", metavar="DIRECTORY",
                      default=None, help =
                      ("Store a cache of results from http requests in "
                       "DIRECTORY. The default is not to use a cache. If "
                       "some cache-policy is set (see below), the default is "
                       "'%s'."% defaultcachedir))
    
    parser.add_option("--cache-policy", dest="cachepolicy", metavar="POLICY",
                      default=None, help =
                      ("Cache-policy to use. Can be one of %s. "
                       "The default is %s."
                       % (", ".join(map(repr, cachepolicies)),
                          cachepolicies[defaultcachepolicy])))

    options, args = parser.parse_args()

    if options.cachepolicy is not None:
        value = options.cachepolicy.lower()
        if value in cachepolicies:
            options.cachepolicy = cachepolicies.index(value)
        else:
            sys.stderr.write("Unknown cache-policy: %s\n" %
                             repr(options.cachepolicy))
            sys.exit(1)

    if args:
        parser.error("Unknown argument(s): " + ", ".join(map(repr, args)))

    if options.days < 1:
        parser.error("--days should be at least 1")
    if options.days > maxdays:
        sys.stderr.write("--days can be at most %d. Using --days=%d" % 
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
        print "cache"
        sys.exit(0)

    return options
options = parseOpts()

# ensure that we can do Danish characters on stderr
sys.stderr = codecs.getwriter(locale.getpreferredencoding())(sys.stderr)

if options.verbose:
    log = sys.stderr.write
else:
    log = lambda x: x

# ---------- Læs fra konfigurationsfil ---------- #

if not (options.listchannels or options.configure):
    try:
        try: 
            lines = codecs.open(options.configfile, "r", "utf-8").readlines()
        except UnicodeDecodeError:
            lines = codecs.open(options.configfile, "r", "iso-8859-1").readlines()
    except IOError, e:
        print u"Cannot open configurefile '%s' for input: %s." % (
            options.configfile, e.strerror)
        print u"Use --configure to configure the grabber."
        sys.exit(1)
        
    chosenChannels = []
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("cache-policy"):
            val = line[len("cache-policy"):].strip()
            if val.lower() not in cachepolicies:
                sys.stderr.write("Unknown cache-policy in line %d: %s\n"
                                 % (i+1,repr(val)))
                sys.exit(1)
            if options.cachepolicy is None: # i.e., not set from commandline
                options.cachepolicy = cachepolicies.index(val.lower())
            continue

        if line.startswith("cache-directory"):
            val = line[len("cache-directory"):].strip()
            if options.cachedir is None: # i.e., not set from commandline
                options.cachedir = val
            continue
                
        if line.startswith("channel"):
            line = line[len("channel"):].strip()
        if line and not line[0] == "#":
            id, name = line.split(" ",1)
            # check that id is an int
            try:
                idn = int(id)
                chosenChannels.append((id, name))
            except ValueError:
                # id is not an int
                sys.stderr.write("Skipping unknown channel-id in line %d: %s\n"
                                 % (i+1,id))

# ensure valid cache settings
if options.cachepolicy is None:
    # no cache policy set
    options.cachepolicy = cachepolicies.index("smart")
    log("Setting cache policy to: %s\n" %
        cachepolicies[options.cachepolicy])
if options.cachepolicy > 0 and options.cachedir is None:
    # no cachedir is set
    options.cachedir = defaultcachedir
    log("Setting cache directory to: %s\n" % options.cachedir)

if options.cachedir is not None:
    if not os.path.isdir(options.cachedir):
        try:
            os.makedirs(options.cachedir)
        except IOError:
            sys.stderror.write("Cannot create cache directory '%s'.\n" %
                               options.cachedir)
            sys.exit(1)

# ---------- Urlopen via cachen ---------- #

# (minimum-cache-policy-level-to-save-this, prefix-filename, prefix-url)
url2fn = [
    (1, "ontv-sta-logo-",  "http://ontv.dk/extern/widget/kanalLogo.php?id="),
    (1, "ontv-dyn-prg-",   "http://ontv.dk/programinfo/"),
    (2, "ontv-dyn-day-",   "http://ontv.dk/?s=tvguide_kanal&guide=&type=&kanal="),
    (2, "ontv-sta-other-", "http://ontv.dk/"),
    (3, "ontv-somewhere-", "http://"), # we should never reach this line
    ]

def cleanCache():
    """If are using smart-cache: Delete all files in the cache that are
    older than maxdays+1.5 days. o.w., do nothing."""
    global options
    global url2fn
    global maxdays

    if options.cachepolicy != 1:
        return
    log("Cleaning cache: %s\n" % options.cachedir)
    count = 0
    
    res = [re.escape(pre) + ".*" for _,pre,_ in url2fn]
    r = "^(%s)\.gz$" % "|".join(res)
    r = re.compile(r)

    old = time.time() - (maxdays+1.5)*24*3600

    root = options.cachedir
    for fn in sorted(os.listdir(root)):
        if r.match(fn) and os.path.isfile(fn):
            lfn = os.path.join(root, fn)
            ftime = os.lstat(lfn).st_mtime
            if ftime < old:
                os.unlink(lfn) # delete it
                count += 1
    
    if count == 1:
        log("Cleaning done: %d old file deleted\n" % count)
    else:
        log("Cleaning done: %d old files deleted\n" % count)

if not (options.configure or options.listchannels):
    cleanCache()

def urlFileName(url):
    """Return (level-to-save-this, filename)"""
    global options
    global url2fn

    for (level, pre, preurl) in url2fn:
        if url.startswith(preurl):
            break
    else:
        assert(False)
    fn = pre + urllib.quote_plus(url[len(preurl):]) + ".gz"

    return (level, os.path.join(options.cachedir, fn))

def urlopen(url, forceRead = False):
    """urlopen(url, forceRead) -> (cache-was-used, data-from-url)

    If forceRead is True and using smart cache policy, then read url even
    if a cached version is available"""
    global options

    level, fn = urlFileName(url)
    if level <= options.cachepolicy:
        if os.path.isfile(fn) and not (forceRead and options.cachepolicy==1):
            # log("Using data in %s\n" % fn)
            data = gzip.open(fn).read()
            return (True, data)
        else:
            # not in cache
            try:
                data = urllib2.urlopen(url).read()
            except urllib2.HTTPError:
                return (False, None)

            if data:
                fd = gzip.open(fn, "wb")
                fd.write(data)
                fd.close()

            return (False, data)
    else:
        # cache should not be used
        try:
            data = urllib2.urlopen(url).read()
        except urllib2.HTTPError:
            return (False, None)
        return (False, urllib2.urlopen(url).read())
        

# ---------- Lav kanal liste ---------- #
def parseChannels():
    """Returns a list of (channelid, channelname) for all available
    channels"""
    kanaldata = urlopen("http://ontv.dk/")[1]
    kanaldata = kanaldata.decode("iso-8859-1")
    kanalliste = []
    lande = re.findall('div id="channels([A-Z]{2})"', kanaldata)
    for land in lande:
        start = kanaldata.find('div id="channels%s"' % land)
        end = kanaldata.find('div id="channels', start+1)
        if end < 0:
            end = kanaldata.find("<script",start+1)
        kanaler = re.findall(r'<a href="/tv/(\d+)"[^<>]*?>([^<>]+?)</a>',
                             kanaldata[start:end], re.DOTALL)
        for id, navn in kanaler:
            kanalliste.append((int(id), land+"_"+navn))
    kanalliste.sort()
    return kanalliste

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

def ts2string(tt, is_dst = -1):
    global mytz
    
    dt = mytz.localize(datetime.datetime(*tt[:6]), is_dst)
    return dt.strftime("%Y%m%d%H%M%S %z")

# warn if we are running in the middle of the night
if 4 <= time.localtime()[3] < 6:
    log("Warning: You may get unexpected results when running "
        "this script between 04:00 and 06:00.\n")

# ---------- Funktioner til parsing ---------- #

def noon(day):
    """Return time tuple curresponding to noon of day, 
    e.g. (2008,12,31,12,0,0,0,1,-1))"""
    now = time.localtime() 
    noon = time.mktime(now[:3] + (12,0,0,0,1,-1))
    if 0 <= now[3] <= 5: 
        day -= 1
    return time.localtime(noon + day * 24*3600)[:3] + (12,0,0,0,1,-1)

def parseDay (day):
    n = noon(day)
    date = time.strftime("%Y-%m-%d", n)
    return date

def jumptime (days = 0, hours = 0, minutes = 0):
    # first find correct day
    day = noon(days)[:3]
    return day + (hours,minutes,0,0,1,-1)

cdataexpr = re.compile(r"<!\[CDATA\[([^<>]*)\]\]>")
retries = 3
def readUrl (url, forceRead = False):
    """readUrl(url, forceRead) -> (cache-was-used, data-from-url)
    
    If forceRead is True and using smart cache policy, then read url even
    if a cached version is available"""
    for i in range (retries):
        try:
            cu, data = urlopen(url, forceRead)
            if not data:
                continue
            data = cdataexpr.sub(r"\1", data)
            return (cu,data)
        except: pass
    return (False, None)

import htmlentitydefs
k = map(len,htmlentitydefs.entitydefs.keys())
ampexpr = re.compile("&(?![a-zA-Z0-9]{%d,%d};)" % (min(k),max(k)))

dayexpr = re.compile(r'(\d\d)[:.](\d\d):</p>(?:.*?)<a href="/programinfo/(\d+)">(.*?)\s*</a>')
startendexpr = re.compile('(\d\d)[:.](\d\d) - (\d\d)[:.](\d\d)')
infoexpr = re.compile(r'(?:<p><strong>|<td><p style="margin-top:0px;">)(.*?)</p><p>', re.DOTALL)
imgexpr = re.compile(r'src="(http://ontv.dk/imgs/print_img.php.*?)"')
extraexpr = re.compile(r'<strong>(.*?):</strong>\s*(.*?)<')
starexpr = re.compile(r'<img src="http://udvikling.ontv.dk/imgs/stars/(full|half).gif" />')
largetitleexpr = re.compile(r's=tvguide_search&search=([^"]*?)"\s+title=')

def parseLarge(day, tz, data):
    # parse information available in data if possible o.w. return None

    title = largetitleexpr.search(data)    
    if not title:
        return None
    title = urllib.unquote(title.group(1)).decode("iso-8859-1")

    start = data.rfind('<div class="content"')
    end = data.find('class="titles">Brugernes mening',start)
    if end < 0: end = data.find("<iframe",start)
    data = data[start:end].decode("iso-8859-1")
    data = ampexpr.sub("&amp;",data)
    
    times = startendexpr.search(data)
    if not times:
        return None

    stars = starexpr.findall(data)
    extra = extraexpr.findall(data)
    info = infoexpr.search(data)
    img = imgexpr.search(data)
    
    return parseData(title, stars, extra, times, info, img, day, tz)

def getDayProgs (id, day):
    data = readUrl("http://ontv.dk/?s=tvguide_kanal&guide=&type=&kanal=%s&date=%s" % (id, parseDay(day)))[1]
    if not data:
        log("[-No data available for day %s-]" % day)
        yield []; return
    
    data = data.decode("iso-8859-1")
    start = data.find('<tr style="background-color:#eeeeee;">')
    end = data.find("</table>",start)
    
    programmes = dayexpr.findall(data, start, end)
    if not programmes:
        log("[-No data available for day %s-]" % day)
        yield []; return

    # check for summer -> winter tz at 02:00 -> 02:59
    # this is detected when program i starts "after" program i+1
    for i in range(1,len(programmes)):
        # format: (sh, sm, info, title) = p
        pp, p = programmes[i-1:i+1]
        if int(pp[0]) == 2 and int(p[0]) == 2 and \
           int(pp[1]) > int(p[1]):
            # there must have been a tz change:
            tzDefault = lambda j, first=i: j < first
            log("Summer/winter tz change detected\n")
            break
    else:
        tzDefault = lambda j: -1 # no tzchange detected
    
    last = 0
    for i in range(len(programmes)):
        sh, sm, info, title = programmes[i]
        tz = tzDefault(i)
        if int(sh) < last: day += 1
        last = int(sh)

        small = parseSmallData(sh, sm, title, day, tz)
        cused, data = readUrl("http://ontv.dk/programinfo/%s" % info)
        if not data:
            log("\nTimeout for program %s\n" % info)
            yield small
            continue

        large = parseLarge(day, tz, data)
        if not large:
            log("\nCannot parse infomation for program %s\n" % info)
            yield small
            continue
        
        # keys required to be the same in small and large for us to trust
        # the cached copy
        keys = ("titleda", "start") 
        smk = [small[key] for key in keys]
        lak = [large[key] for key in keys]
        if smk != lak:
            if not cused:
                log("Warning: Unexpected %s != %s\n" % (str(smk),str(lak)))
                yield large
            else:
                # cache is maybe not new enough - force a reread
                #log("Flushing cached copy, since %s != %s\n" % 
                #    (str(smk),str(lak)))
                log("!")
                cu_data = readUrl("http://ontv.dk/programinfo/%s" % info, True)
                if not cu_data or not cu_data[1]:
                    log("\nTimeout for program %s\n" % info)
                    yield small
                else:
                    large = parseLarge(day, tz, cu_data[1])
                    if large:
                        yield large
                    else:
                        yield small
        else:
            yield large

ampexpr = re.compile(r"&(?![\w#]+;)")
brexpr = re.compile(r"<\s*br\s*/\s*>", re.IGNORECASE)
def fixText (text):
    text = text.replace("<strong>","")
    text = text.replace("</strong>","\n")
    text = ampexpr.sub("&amp;",text)
    text = brexpr.sub("",text).strip()
    if text.endswith("."): text = text[:-1]
    return text

def parseData (title, stars, extras, times, info, img, day, tz):
    dic = {}
    
    parseTitle(fixText(title), dic)
    if info: parseInfo(info.groups()[0], dic)
    if extras: parseExtras(extras, dic)
    if stars: parseStars(stars, dic)
    if img: dic["icon"] = img.groups()[0]
    
    sh, sm, eh, em = map(int, times.groups())
    day = int(day)
    st = jumptime(day, sh, sm)
    tt = jumptime(day, eh, em)
    sz = ez = tz
    if (eh,em) < (sh,sm):
        if eh == sh == 2:
            # we are going from summer to winter time during this program
            sz,ez = True, False
        else:
            # we are simply passing midnight
            tt = jumptime(day+1,eh,em)

    dic["start"] = ts2string(st, sz)
    dic["stop"] = ts2string(tt, ez)
    
    return dic

def parseSmallData (sh, sm, title, day, tz):
    dic = {}
    parseTitle(fixText(title), dic)
    dic["start"] = ts2string(jumptime(int(day), int(sh), int(sm)), tz)
    return dic

maxStars = 10
def parseStars (stars, dic):
    noStars = 0
    for star in stars:
        if star == "full": noStars += 2
        elif star == "half": noStars += 1
    if noStars > maxStars:
        log(str(dic)+" \t"+str(stars))
    dic["stars"] = str(noStars)

titleexpr = re.compile(r'^(.*?)(?:\s+(med\s+.*?))?(?:\s*\(\s*(\d+)*\s*:?\s*(\d+)*\s*\)\s*[-:]?\s*(.*?))?(?:\s+-\s*(.*?))?(?::\s*(.*?))?(?:\s*\(\s*(\d+)*\s*:?\s*(\d+)*\s*\))?$')
def parseTitle (title, dic):
    """Udgave med support for title, med subtitle, (episode:antal), :subtitle, - subtitle, :subtitle og (episode:antal) """
    orgtitle = title

    if title.endswith("16:9"):
        dic["format"] = "16:9"
        title = title[:-4].strip()
    if title.endswith("Surround"):
        dic["surround"] = True
        title = title[:-8].strip()
    if title.endswith("UTXT"):
        dic["utxt"] = True
        title = title[:-4].strip()
    if title.endswith("(G)"):
        #dic["shown"] tags ikke i brug, selv om dtden tillader <previously-shown/> uden start="..." attribute. 
        #Den tages ikke i brug, da mergeren ikke kan overskrive den fra en anden fil med start="..." attribute.
        title = title[:-3].strip()
    if title.startswith("Fredagsfilm:"):
        title = title[12:].strip()
    
    m = titleexpr.match(title)
    if m == None:
        dic["titleda"] = title
        log(u"Could not parse the title \"%s\"\n" % title)
        return
        
    title, sub, ep, af, sub1, sub2, sub3, ep1, af1 = m.groups()
    dic["titleda"] = title
    
    for s in (sub, sub1, sub2, sub3):
        if s:
            dic["sub-titleda"] = s
            break

    if ep == ep1 == None: return
    elif ep == None and ep1 != None:
        ep = ep1; af = af1
    if af == None: af = ""
    else: af = "/"+af
    dic["episode"] = ".%s%s." % (str(ep),str(af))

simptitleexpr = re.compile(r'^(.*?)(?:\s+-\s*(.*?))?(?::\s*(.*?))?$')
def simpleParseTitle (title, dic):
    """Udgave med support for title, -subtitle og :subtitle"""
    orgtitle = title
    
    m = simptitleexpr.match(title)
    if m == None:
        dic["title"] = title
        log(u"Could not 'simple'parse the title \"%s\"\n" % title)
        return
        
    title, sub, sub1 = m.groups()
    dic["title"] = title
    
    for s in (sub, sub1):
        if s:
            dic["sub-title"] = s
            break

linkexpr = re.compile(r'\s*<a(?:.*?)>\s*(.*?)\s*</a>\s*')
def splitPersons (persons):
    persons = linkexpr.sub(r'\1 ', persons)
    persons = persons.split(", ")
    loc = persons[-1].find(" og ")
    if loc >= 0:
        persons.append(persons[-1][loc+4:])
        persons[-2] = persons[-2][:loc]
    return [p.strip() for p in persons]

def count (string, char):
    i = 0
    for c in string:
        if c == char: i += 1
    return i

def put (key, value, dic):
    if key in dic:
        dic[key] += value
    else: dic[key] = value

creditsDic = {"medvirk":"actor", "endvidere":"actor", u"vært":"presenter", "manuskript":"writer", "instruktion":"director", u"instruktør":"director", "foto":"adapter", "scenografi":"adapter", "signaturmusik":"adapter", "musik":"adapter", "kommentator":"commentator", "tekst":"adapter", "producer":"producer", "produktion":"producer", u"tilrettelæggelse":"adapter", u"gæst":"guest"}
dateexpr = re.compile(r' fra (\d\d\d\d)')
stripexpr  = re.compile(r'(:|,|og)\s*\r')
stripexpr2 = re.compile(r'\r\s*(:|,|og)')
monthdic = { "januar":"1", "jan":"1", "februar":"2", "feb":"2", "marts":"3", "mar":"3", "april":"4", "apr":"4", "maj":"5", "juni":"6", "jun":"6", "juli":"7", "jul":"7", "august":"8", "aug":"8", "september":"9", "sep":"9", "oktober":"10", "okt":"10", "november":"11", "nov":"11", "december":"12", "dec":"12" }
timeexpr = re.compile("\d+|"+"|".join(monthdic.keys()))

def parseInfo (info, dic):
    info = fixText(info)
    isBad = lambda c: ord(c) < ord(" ") and c != "\n" and c != "\r"
    info = "".join([c for c in info if not isBad(c)])
    info = stripexpr.sub(r'\1 ', info)
    info = stripexpr2.sub(r' \1', info)
            
    normal = []
    for line in [l.strip() for l in info.splitlines()]:
        while line:
            line = line.strip()
            linel = line.lower()
            for (tag, key, value) in [
                ("16:9", "format", "16:9"),
                ("breitbild", "format", "16:9"),
                ("surround", "surround", True),
                ("stereo", "stereo", True),
                ("utxt", "utxt", True),
                ("videotext", "utxt", True),
                ]:
                if linel.startswith(tag):
                    dic[key] = value
                    line = line[len(tag):]
                    break
                if linel.endswith(tag):
                    dic[key] = value
                    line = line[:-len(tag)]
                    break
            else:
                break

        if not line: continue

        if line.startswith(u"Sendes også"):
            continue
        if line.startswith(u"Vises i bredformat"):
            dic["format"] = "16:9"
            continue
        if (line[0] == "(" and (line[-1] == ")" or line.endswith(")."))) and \
                not line.startswith("(Vom"):
            simpleParseTitle(line[1:-1], dic)
            continue
        if line[0] == '"' and line[-1] == '"' and not "sub-title" in dic:
            dic["sub-title"] = line[1:-1]
            continue
        if line[:2] == '- ' and line[-1] == '.' and not "sub-title" in dic:
            dic["sub-title"] = line[2:-1]
            continue
        if line.startswith(u"Sendt første gang"):
            t = line[18:].strip()
            parts = timeexpr.findall(t)
            if len(parts) == 4:
                # Sometimes "Sendt første gang" and "Sendes også..."
                # are on the same line.
                d, m, _, _ = parts
                y = time.strftime("%y")
            elif len(parts) == 3:
                d, m, y = parts
            elif len(parts) == 2:
                d, m = parts
                y = time.strftime("%y")
            elif len(parts) == 1:
                d = "1"
                m = "1"
                y, = parts
            else:
                # Ignorér ikke-genkendt tidsstempel
                continue
            if not m.isdigit():
                m = monthdic[m]
            ot = t
            t = ".".join(s[-2:].zfill(2) for s in (d, m, y))
            try: 
                t = addTimeZone(time.strftime("%Y%m%d",time.strptime(t,"%d.%m.%y")))
                dic["shown"] = t
            except ValueError, msg:
                if options.verbose:
                    # sometimes we get illegal time stamps like 31.11
                    sys.stderr.write("Unable to parse timestampe, %s: %s\n" % (ot,msg))
            continue
        
        # Del der fixer linjer som
        # Amerikansk komedie fra 1996.
        # Amerikansk drama fra 1996 med Woody Harrelson.
        # Dansk romantisk dramaserie fra 2002.
        # Dramadokumentarserie fra BBC fra 2005.
        m = dateexpr.search(line) #' fra (\d\d\d\d)'
        if m != None:
            dic["date"] = m.groups()[0]
            start, end = m.span()
            dele = line[:start].split(" ")
            if "fra" in dele:
                dele = dele[:dele.index("fra")]
            while len(dele) > 2:
                del dele[1]
            if len(dele) == 2:
                dic["country"] = dele[0]
                dic["categoryda"] = dele[1]
            elif len(dele) == 1:
                dic["categoryda"] = dele[0]
        
        # Del der fixer linjer som
        # Medvirkende:
        # Nikolaj: Peter Mygind.
        # Endvidere medvirker:
        # Birgitte Simonsen, Ole Thestrup,
        # Signaturmusik:Tim Christensen.
        # Danske kommentatorer: Mads Vangsø og Adam Duvå Hall.

        def inIt (var, dic):
            """Tester om var "indeholder" en af nøgler i dic'et"""
            var = var.lower()
            for k, v in [(k.lower(),v) for k,v in dic.iteritems()]:
                if var.find(k) >= 0:
                    return v
            return ""
        
        import string
        def couldbePerson (person):
            if len(person) < 2: return False
            uniletters = "".join([unichr(i) for i in range(192,564)])
            ok = string.letters+" .'-&:\"()/"+uniletters
            for char in person:
                if not char in ok:
                    return False
            if count(s[1]," ") >= 5:
                return False
            return True
        
        s = [t.strip() for t in line.split(":") if t.strip()]
        if len(s) >= 2:
            if len(s[1]) > 0:
                if s[1][-1] == ".": s[1] = s[1][:-1]
            if s[0] in creditsDic:
                put(creditsDic[s[0]], splitPersons(":".join(s[1:])), dic)
            else:
                t = inIt(s[0], creditsDic)
                if t: put(t, splitPersons(":".join(s[1:])), dic)
                elif len(s) == 2 and couldbePerson("".join(s)):
                    put("actor", ["%s: %s"%(s[0],s[1])], dic)
                else: normal.append(line)
            continue
        
        normal.append(line)
    
    if normal:
        put ("descda", "\n".join(normal), dic)

episodeexpr = re.compile("(\d+)\s*(?:av|af|:|/)?\s*(\d+)?")
def parseExtras (extras, dic):
    for key, value in [(k.lower(),fixText(v)) for k,v in extras]:
        if key == 'medvirkende':
            put("actor", splitPersons(value), dic)
        elif key == 'genre':
             dic["categoryda"] = value
        elif key == 'type' and not "categoryda" in dic:
            dic["categoryda"] = value
        elif key == 'fra':
            year_country = value.split(None,1)
            for item in year_country:
                if item[:4].isdigit():
                    dic["date"] = item[:4]
                else:
                    dic["country"] = item
        elif key == "episode":
            m = episodeexpr.search(value)
            if m:
                ep, af = m.groups()
                if af:
                    dic["episode"] = ".%s/%s." % (af, ep)
                else:
                    dic["episode"] = ".%s." % ep

def getChannelIcon (url):
    d = readUrl(url)
    if not d: return None
    _, page = d
    s = len("<img src=\"")
    e = page.find("\"", s)
    return page[s:e]

# ---------- Spørg til konfigurationsfil ---------- #

if options.configure:
    # ensure that we can do Danish characters
    sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)
    folder = os.path.dirname(options.configfile)
    print u"The configuration will be saved in '%s'." % options.configfile
    if not os.path.isdir(folder):
        os.makedirs(folder)
    if os.path.exists(options.configfile):
        answer = raw_input(u"'%s' does already exist. Do you want to overwrite it? (y/N) " % options.configfile).strip().lower()
        if answer != "y":
            sys.exit()
            
    lines = ["#  -*- encoding: utf-8 -*-\n"]

    print
    print "This grabber can use a cache for files that it has already"
    print "downloaded - this greatly decreases the running time after"
    print "the program has been used for the first time."
    print
    while True:
        print "Do you want to use a cache?"
        assert(len(cachepolicies) == 3)
        opts = [("%d) %s - never use a cache",
                "%d) %s - use a cache whenever this makes sense",
                "%d) %s - always use the cache (only for debugging)",
                 )[i] % (i,cachepolicies[i]) for i in range(len(cachepolicies))]
        opts[defaultcachepolicy] += " (default)"
        print "\n".join(opts)
        answers = map(str, range(len(cachepolicies)))
        answer = raw_input(u"Policy (%s) " % "/".join(answers)).strip()
        if not answer: answer = str(defaultcachepolicy)
        if answer in answers:
            cpol = cachepolicies[int(answer)]
            break
        else:
            print "%s is not a valid answer" % repr(answer)
            print
    if cpol != cachepolicies[0]:
        # get the directory as well
        cdir = raw_input("Directory to store the cache in [%s]:"
                         % defaultcachedir).strip()
        if not cdir:
            cdir = defaultcachedir
        lines.extend(["cache-policy %s\n" % cpol,
                      "cache-directory %s\n" % cdir])
    print
    print "Reading channel data from the internet."
    for id, name in parseChannels():
        answer = raw_input(u"Add channel %s (y/N) " % name).strip()
        if answer == "y":
            lines.append(u"channel %d %s\n" % (id, name))
        else:
            lines.append(u"# channel %d %s\n" % (id, name))
    codecs.open(options.configfile, "w", "utf8").writelines(lines)
    sys.exit()
    
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
    channelList = parseChannels()
    print u'<?xml version="1.0" encoding="UTF-8"?>'
    print u"<!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
    print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"
    
    for id, channel in channelList:
        print u"<channel id=\"%s\">" % id 
        print u"    <display-name>%s</display-name>" % fixText(channel)
        iconurl = getChannelIcon("http://ontv.dk/extern/widget/kanalLogo.php?id=%s" % id)
        if iconurl:
            print "    <icon src=\"%s\"/>" % iconurl
        print "</channel>"
    print u"</tv>"
    sys.exit(0)

# ---------- Parse ---------- #

keyDic = {"titleda":"<title lang=\"da\">", "sub-titleda":"<sub-title lang=\"da\">", "title":"<title>", "sub-title":"<sub-title>", "categoryda":"<category lang=\"da\">", "descda":"<desc lang=\"da\">", "episode":"<episode-num system=\"xmltv_ns\">", "format":"<video><aspect>", "date":"<date>", "country":"<country>", "stars":"<star-rating><value>", "shown":"<previously-shown start=\"", "icon":"<icon src=\""}

endDic = {"titleda":"</title>", "sub-titleda":"</sub-title>", "title":"</title>", "sub-title":"</sub-title>", "categoryda":"</category>", "descda":"</desc>", "episode":"</episode-num>", "format":"</aspect></video>", "date":"</date>", "country":"</country>", "stars":"/%d</value></star-rating>" % maxStars, "shown":"\" />", "icon":"\" />"}

oneDic = {"utxt":"<subtitles type=\"teletext\" />",
          "surround": "<audio><stereo>surround</stereo></audio>",
          "stereo": "<audio><stereo>stereo</stereo></audio>",
          }

credits = ("director", "actor", "writer", "adapter", "producer",
                   "presenter", "commentator", "guest")

log("Parsing data: \n")
print u"<?xml version=\"1.0\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

for id, channel in chosenChannels:
    print "<channel id=\"%s\">" % id
    print "    <display-name>%s</display-name>" % fixText(channel)
    iconurl = getChannelIcon("http://ontv.dk/extern/widget/kanalLogo.php?id=%s" % id)
    if iconurl: print "    <icon src=\"%s\"/>" % iconurl
    print "</channel>"

for id, channel in chosenChannels:
    log("\n%s:"%channel)

    for day in range(options.offset, min(options.offset+options.days,maxdays)):
        log(" %d" % day)
        for programme in getDayProgs(id, day):
            if not programme: continue
            print u"<programme channel=\"%s\" start=\"%s\"" % (id, programme["start"]),
            if "stop" in programme: print u" stop=\"%s\">" % programme["stop"]
            else: print ">"
    
            for key, value in keyDic.iteritems():
                if programme.has_key(key):
                    print u"%s%s%s" % (keyDic[key], programme[key], endDic[key])
        
            if len([c for c in credits if c in programme]) > 0:
                print u"<credits>"
                for c in credits:
                    if programme.has_key(c):
                        for credit in programme[c]:
                            print u"<%s>%s</%s>" % (c,credit,c)
                print u"</credits>"

            for k, v in oneDic.iteritems():
                if k in programme:
                    print u"%s" % v.decode("utf8")

            print u"</programme>"
    
print u"</tv>"

log(u"\nDone.\n")
