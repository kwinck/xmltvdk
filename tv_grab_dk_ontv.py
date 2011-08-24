#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Fetch tv programme data from ontv.dk
#
# ----------------------------------------------------------------------------
# "THE BEER-WARE LICENSE" (Revision 42):
# http://svalgaard.net/jens/ wrote this file. As long as you retain
# this notice you can do whatever you want with this stuff. If we
# meet some day, and you think this stuff is worth it, you can buy me
# a beer in return, Jens Svalgaard Kohrt
# ----------------------------------------------------------------------------
#
# (c) 2008-2011 http://svalgaard.net/jens/
#
VERSION = "$Id$"

import copy
import codecs
import datetime
import gzip
import htmlentitydefs
import locale
import optparse
import os
import re
import socket
import stat
import string
import sys
import time
import urllib
import urllib2
import xml.sax.saxutils
escape = xml.sax.saxutils.escape
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
            sys.stderr.write("Possible cache-policies: %s\n" % ", ".join(cachepolicies))
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

# ---------- Setup stderr og stdout ----------

def getNiceEncoding():
    enc = locale.getpreferredencoding()
    
    # try to write æøå to this and see if we fail
    try:
        x = u'æøåÆØÅá'.decode(enc)
    except UnicodeEncodeError, u:
        # ignore the locale since this does not allow us to write what we want
        enc = 'UTF-8'
    return enc

# ensure that we can do Danish characters on stderr
sys.stderr = codecs.getwriter(getNiceEncoding())(sys.stderr)

if options.verbose:
    log = sys.stderr.write
else:
    # simply ignore this
    log = lambda x: x
error = sys.stderr.write

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
                error("Unknown cache-policy in line %d: %s\n" % (i+1,repr(val)))
                error("Possible cache-policies: %s\n" % ", ".join(cachepolicies))
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
            cid, name = line.split(" ",1)
            if not re.match('[-a-z0-9]*',cid):
                log("Skipping unknown channel-id in line %d: %s\n" % (i+1,cid))
            else:
                chosenChannels.append((cid, name))

# ensure valid cache settings
if options.cachepolicy is None:
    # no cache policy set
    options.cachepolicy = cachepolicies[defaultcachepolicy]
    log("Setting cache policy to: %s\n" %
        options.cachepolicy)
if options.cachepolicy > 0 and options.cachedir is None:
    # no cachedir is set
    options.cachedir = defaultcachedir
    log("Setting cache directory to: %s\n" % options.cachedir)

if options.cachedir:
    if not os.path.isdir(options.cachedir):
        try:
            os.makedirs(options.cachedir)
        except IOError:
            log("Cannot create cache directory '%s'.\n" % options.cachedir)
            sys.exit(1)

# ---------- URL templates --------------- #
#
# http://ontv.dk/tv-guide/6eren/2011-03-10
# http://ontv.dk/info/100661299756900-ti-tommelfingre
#

ROOT_URL        = "http://ontv.dk/"
CHANNELS_URL    = ROOT_URL + "ajax/channel_list.php?language=%s"
CHANNEL_DAY_URL = ROOT_URL + 'tv-guide/%s/%s'
PROGRAMME_URL   = ROOT_URL + "info/%s"

def getDayURL(channelId, day):
    '''Return e.g., http://ontv.dk/tv-guide/6eren/2011-03-10'''
    global CHANNEL_DAY_URL
    return CHANNEL_DAY_URL % (channelId, parseDay(day))

def getProgrammeURL(programmeId):
    global PROGRAMME_URL
    return PROGRAMME_URL % programmeId

# ---------- Urlopen via cachen ---------- #

# (minimum-cache-policy-level-to-save-this, prefix-filename, prefix-url)
url2fn = [
    (1, "ontv-sta-logo-",  "http://ontv.dk/imgs/epg/logos/"),
    (1, "ontv-dyn-prg-",   "http://ontv.dk/info/"),
    (2, "ontv-dyn-day-",   "http://ontv.dk/tv-guide/"),
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
    files = sorted(os.listdir(root))
    for fn in files:
        lfn = os.path.join(root, fn)
        if r.match(fn) and os.path.isfile(lfn):
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

    # either not in cache or cached version should not be used
    try:
        data = urllib2.urlopen(url).read()
    except urllib2.HTTPError:
        return (False, None)

    # should we save this in our cache?
    if level <= options.cachepolicy:
        fd = gzip.open(fn, "wb")
        fd.write(data)
        fd.close()

    return (False, data)

def readUrl(url, forceRead = False):
    """readUrl(url, forceRead) -> (cache-was-used, data-from-url)

    If forceRead is True and using smart cache policy, then read url even
    if a cached version is available.

    Data is always returned as a unicode string"""
    RETRIES = 3
    for i in range (RETRIES):
        try:
            cu, data = urlopen(url, forceRead)
            if not data:
                continue
            data = data.decode('utf-8')
            return (cu,data)
        except: pass
    return (False, None)

# ---------- Lav kanalliste ---------- #
def parseChannels():
    """Returns a list of (channelid, channelname) for all available
    channels"""
    global ROOT_URL, CHANNELS_URL
    
    # find list of languages/groups
    data = readUrl(ROOT_URL)[1]
    languages = re.findall(r"showChannels\('(..)'\);",data)

    # walk through all "languages"
    channels = []
    for lang in languages:
        data = readUrl(CHANNELS_URL % lang)[1]
        for (no,desc) in re.findall(r'<a href="/tv-guide/([^"]+)">([^<]+)</a>',data):
            channels.append((no, desc + " " + lang.upper()))
    channels.sort(key = lambda x: x[1].strip().lower())
    return channels

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
        log("Warning: Cannot find time zone for %s.\n" % repr(ts))
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

def jumptime (days = 0, hours = 0, minutes = 0, tz = -1):
    # first find correct day
    day = noon(days)[:3]
    return day + (hours,minutes,0,0,1,tz)

#xxx
def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == u"&#":
            # character reference
            try:
                if text[:3] == u"&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub(u"&#?\w+;", fixup, text)

def compact(s, alsoLineBreaks = False):
    s = unescape(s)
    if alsoLineBreaks:
        s = re.sub("[\n\r]+"," ", s)
    s = re.sub("[ \t]+"," ", s)
    s = re.sub("> ",">",s)
    s = re.sub(" <","<",s)
    return s.strip()

class Tag:
    def __init__(self, name, text = '', parent = None):
        if "_" in name and "=" in name:
            sp = name.split("_",1)
            self.name = sp[0]
            sp = sp[1].split("=",1)
            self.attr = [(sp[0], sp[1])]
        else:
            self.name = name
            self.attr = [] # [(k,v), (k,v), ...]
        self.children = []
        self.parent = parent
        self.setText(text)

    def setText(self, text):
        if 'title' in self.name:
            text = text.strip(".")
            for ig in ['Fredagsfilm:',':','.','(G)','(g)']:
                while text.startswith(ig):
                    text = text[len(ig):].strip()
                while text.endswith(ig):
                    text = text[:-len(ig)].strip()
            m = re.match(ur'(.*?) ?\((\d+)\)', text)
            if m:
                text = m.group(1)
                self.parent.addTag('episode-num_system=xmltv_ns', '.%s.' % (int(m.group(2))-1))
        self.text = text

    # attributes
    def __setitem__(self, key, value):
        '''Set attribute on this tag'''
        # check if the attribute is already set
        for i in range(len(self.attr)):
            if self.attr[i][0] == key:
                # found it!
                self.attr[i] = (key,value)
                break
        else:
            self.attr.append((key,value))
    def __getitem__(self, key):
        for (k,v) in self.attr:
            if k == key:
                return v
        raise KeyError(key)
    
    # children
    def getChild(self, tagname, createIfNotPresent = False):
        for child in self.children:
            if child.name == tagname:
                return child
        if createIfNotPresent:
            return self.addChild(Tag(tagname,'', self))
        return None
    def hasChild(self, tagname):
        for child in self.children:
            if child.name == tagname:
                return child
        return None

    def addChild(self, child):
        '''Add this instance of Tag as a child'''
        assert(isinstance(child, Tag))
        self.children.append(child)
        return child
    def addTag(self, tagname, tagtext = ''):
        ''' tagname can be, e.g, credits:actor or title_da or video:aspect!16:9'''
        cur = self
        if '!' in tagname:
            tagname, tagtext = tagname.split('!')
        tagnames = tagname.split(':') 
        for tn in tagnames[:-1]:
            cur = cur.getChild(tn, True)
        cur.addChild(Tag(tagnames[-1], tagtext, cur))
        return cur

    # print this
    def __unicode__(self):
        return self.toString()
    def toString(self, indent = ''):
        if '_' in self.name:
            tname, lang = self.name.split('_',1)
            attrs = ['lang="%s"' % lang]
        else:
            tname = self.name
            attrs = []
        attrs.extend([u'%s="%s"' % (k,v) for (k,v) in self.attr])
        attrs = u' '.join(attrs)
        if attrs:
            attrs = ' ' + attrs
        t = [escape(s.strip()) for s in self.text.split("\n") if s.strip()]
        
        if not (self.children or t):
            return indent + '<%s%s />\n' % (tname, attrs)

        if self.children:
            res = indent + '<%s%s>%s\n' % (tname, attrs, " ".join(t))
            cs = [c.toString(indent + '  ') for c in self.children]
            # remote duplicates
            rs = {}
            for c in cs:
                if not c in rs:
                    res += c
                rs[c] = 1
            res += indent + '</%s>\n' % tname
        else:
            res = indent + '<%s%s>' % (tname, attrs)
            if len(t) == 1:
                res += '%s</%s>\n' % (t[0], tname)
            else:
                t = "\n".join([indent+'  '+tl for tl in t])
                res += '\n%s\n%s</%s>\n' % (t, indent, tname)
        return res

class Programme(Tag):
    def __init__(self, *args):
        Tag.__init__(self, *args)
        self.next = None
    def setTime(self, tag, timest):
        '''timest has the format [day, start-hour, start-minute, tz]
        where day is an offset relative to today'''
        self.__dict__[tag] = timest
        self[tag] = ts2string(jumptime(*timest))

def slightlystripped(s):
    s = s.replace('\t', ' ')
    s = re.sub('(</?p>|<br ?/?>|</?h[^>]+>|</?t[^>]+>)','\n', s).strip()
    s = s.replace('&nbsp;',' ')
    s = s.replace('&shy;', '-')
    s = re.sub('</?[^>]*>','', s) # remove all tags
    s = re.sub(' *[\r\n]+ *','\n',s)
    s = s.replace('\n-\n','\n')
    return s

def _isNamePart(s):
    '''Return True iff s could be part of a name, e.g., 
    Nielsen von ABBA etc'''
    if s in ['von', 'dff', 'Mr.', 'Dr.']:
        return True
    if s in ['CSI']:
        return False
    for p in ['Mc','Mac','De',"O'"]:
        if s.startswith(p):
            return _isNamePart(s[len(p):])
    # It has to be either Titlecase or UPPERCASE
    if not (s == s.title() or s == s.upper()):
        return False
    if len(s) == 2 and s == s.upper() and s[1] == '.':
        return True
    if re.search(ur'(?u)\W', s) or re.search(ur'[_\d]', s):
        # it contains something which is not a letter
        return False
    return True

def couldBePerson (person):
    '''Test whether a string could be the name of a person'''
    if len(person) < 2 or person.count(" ") >= 6:
        # too short or too long
        return False
    sp = re.split(ur'(?: |-)', person)
    return False not in map(_isNamePart, sp)

def getNames(s):
    '''Returns list of names in the string s. If this does not look like a list
    of names, None is returned'''
    s = s.strip('.').strip()
    for ending in ['mfl', 'm.fl']:
        if s.endswith(ending):
            s = s[:-len(ending)].strip()
    s = re.split(ur'\s*(?:,| og| efter (?:bog|roman) af| &| and)\s+', s)
    if False in map(couldBePerson, s):
        return None
    else:
        return s

# ---------- Filtre der omdanner en bestemt del af beskrivelsen ----------

_filters = {}
def addFilter(ps, filter, *args):
    global _filters
    if ps not in _filters:
        _filters[ps] = []
    _filters[ps].append((filter, args))

def joinWithNextIfEndsWith(prg, all, expr):
    expr = ur'(?m)(%s)\n' % expr
    all = re.sub(expr, ur'\1 ', all)
    return all

def splitByCreditPrefix(prg, all, prefix, addColon = True):
    'Split into mulitiple lines if ...'
    if addColon:
        expr = ur'(?m)((?:%s):)' % prefix
    else:
        expr = ur'(?m)(%s)' % prefix        
    return re.sub(expr, ur'\n\1', all)
    
def endsOrStartsWith(prg, line, rexpr, result):
    '''If a line ends or starts with something maching rexpr, then the
    particular part of the line is removed, and result is added to
    prg'''
    rexpr = ur'(?:%s)'% rexpr # wrap the expression
    rexpr = ur'(^%s|%s\.?$)' % (rexpr, rexpr) # either starting or ending with
    m = re.search(rexpr, line)
    if m:
        s,e = m.start(), m.end()
        if s == 0:
            # found at the beginning of the line
            line = line[e:].strip()
        else:
            line = line[:s].strip()
        res = result and m.expand(result)
        if res:
            prg.addTag(res)
        return line
    else:
        return line

def prefixFilter(prg, line, prefix, func):
    rexpr = ur'(?:^%s)' % prefix
    m = re.search(rexpr, line)
    if not m:
        return line
    start = line[:m.end()].strip()
    rest = line[m.end():].strip()

    return func(prg, line, start, rest)
def addPrefixFilter(prefix, func):
    addFilter(10, splitByCreditPrefix, prefix, False)
    addFilter(70, prefixFilter, prefix, func)


def extractCredit(prg, line, prefix, creditType, keepPrefix):
    '''Prefix is e.g., Vært or Kommentator(?:er)?'''
    if prefix:
        rexpr = ur'(?:^%s:)' % prefix
    else:
        rexpr = ur'(?:^.*?:)'
    m = re.search(rexpr, line)
    if not m:
        return line
    start = line[:m.end()].strip()
    rest = line[m.end():].strip()
    
    names = getNames(rest)

    if not names:
        return line
    if not prefix:
        pnames = getNames(start[:-1])
        if not pnames or len(pnames) != 1 or len(names) != 1:
            return line
    
    for name in names:
        if keepPrefix:
            txt = '%s %s' % (start, name)
        else:
            txt = name
        prg.addTag('credits:%s' % creditType, txt)
    return ''

def addCreditFilter(creditType, prefix, keepPrefix):
    addFilter(10, splitByCreditPrefix, prefix)
    addFilter(80, extractCredit, prefix, creditType, keepPrefix) 

def applyFilters(prg, desc):
    '''Apply all known filters to desc and add information to prg. The
    remaining lines are returned'''
    global _filters

    keys = sorted(_filters.keys())

    for k in [k for k in keys if k < 15]:
        for (f,args) in _filters[k]:
            desc = f(prg, desc, *args)

    lines = desc.split("\n")
    for k in [k for k in keys if 15 <= k < 100]:
        for i in range(len(lines)):
            line, oline = lines[i], None
            while line and oline != line:
                oline = line
                for (f, args) in _filters[k]:
                    line = f(prg, line, *args)
                    if not line:
                        break
            lines[i] = line

    lines = filter(None, lines)
    desc = "\n".join(lines)

    for k in [k for k in keys if k >= 100]:
        for (f,args) in _filters[k]:
            desc = f(prg, desc, *args)

    return desc

def addAllMetaData(prg, desc):
    desc = applyFilters(prg, desc)
    if desc and desc != 'Ingen beskrivelse...':
        prg.addTag('desc', desc)



# pass 0 
# input: lines as one thing
# join multiple lines into one
P = 0
addFilter(P, joinWithNextIfEndsWith, ':')
addFilter(P, joinWithNextIfEndsWith, ' og')

# pass 10
# input: lines as one thing
# split some lines into more

# pass 20 
# per line : redo until line does not change
P = 20
addFilter(P, endsOrStartsWith, ur'4:3', ur'video:aspect!4:3')
addFilter(P, endsOrStartsWith, ur'16:9', ur'video:aspect!16:9')
addFilter(P, endsOrStartsWith, ur'Breitbild', ur'video:aspect!16:9')
addFilter(P, endsOrStartsWith, ur'\(?Vises i bredformat\)?', ur'video:aspect!16:9')

addFilter(P, endsOrStartsWith, ur'\(S/H\)', ur'video:colour!no')

addFilter(P, endsOrStartsWith, ur'Dolby', ur'audio:stereo!surround') 
addFilter(P, endsOrStartsWith, ur'Dolby 5.1', ur'audio:stereo!surround') 
addFilter(P, endsOrStartsWith, ur'Surround', ur'audio:stereo!surround') 
addFilter(P, endsOrStartsWith, ur'\(\([sS]\)\)', ur'audio:stereo!surround')
addFilter(P, endsOrStartsWith, ur'\([sS]\)', ur'audio:stereo!stereo')
addFilter(P, endsOrStartsWith, ur'STEREO', ur'audio:stereo!stereo')
addFilter(P, endsOrStartsWith, ur'Stereo', ur'audio:stereo!stereo')
addFilter(P, endsOrStartsWith, ur'Zweikanalton', ur'audio:stereo!stereo')

addFilter(P, endsOrStartsWith, ur'\(TTV\)', ur'subtitles_type=teletext')
addFilter(P, endsOrStartsWith, ur'UTXT', ur'subtitles_type=teletext')
addFilter(P, endsOrStartsWith, ur'Videotext', ur'subtitles_type=teletext')

addFilter(P, endsOrStartsWith, ur'[\("][Uu]egnet for (?:mindre )?børn[\)"]\.?', ur'rating_system=DK!\1')

addFilter(P, endsOrStartsWith, ur'Sendes samtidig på DR HD', None)



TODO = """
        ("utxt", "utxt", True),
        ("(t)", "utxt", True),
        ("(g)", None, "(G) is not used"),
        ("(fortsat)", None, None),
"""

def fType(prg, line, prefix, rest):
    # Sometimes the category is shown as e.g., Type: serie
    # Genre: Drama/Science-fiction
    # Genre: Musical comedy, drama
    m = re.match(u'^([- a-zA-ZæøåÆØÅ/,]*)\\.?$', rest)
    if m:
        for txt in re.split(' *[/,]+ *', m.group(1)):
            if txt:
                prg.addTag('category',txt.strip())
        return ''
    return line
addPrefixFilter(ur"(?:Genre|Type):", fType)

def fFrom(prg, line, prefix, rest):
    # Fra: 2010 Denmark
    # Fra: 1969 Frankrig & Monaco
    # Fra: 1969 Frankrig/Monaco
    # Fra: 1990-2001 USA
    # Fra: 1990/2001 USA
    # Fra: Tyskland
    # Fra: 2000 USA, Canada
    # Fra:  U.S.A.
    m = re.match(ur'^(\d*(?:[-/]\d+)?) ?([a-zA-Z &,]*)$', rest)
    if not m:
        m = re.match(ur'^(\d*(?:[-/]\d+)?) ?(U.S.A.)$', rest)
    if m:
        year, country = m.groups()
        if year:
            for y in year.replace('/','-').split('-'):
                if y.strip():
                    prg.addTag('date', y)
        if country:
            for c in re.split(ur'[&,/]', country):
                if c.strip():
                    prg.addTag('country_da', c.strip())
        return ''
    return line
addPrefixFilter(ur"Fra:", fFrom)

def fProduction(prg, line, prefix, rest):
    '''
    Produktion: BLU A/S for TV 2|DANMARK, 2010.
    Produktion: BBC, 1997.
    Produktion: Channel 4, 2006.
    Produktion: CBS Productions, Caroline Productions og Moon Water Productions, 1994-2003.
    Produktion: Chuck Lorre Productions i samarbejde med 20th Century Fox, 1998.
    Produktion: 20th Century Fox & CBS, 1999.
    Produktion: Nelvana Ltd./Ellipse Animation, TMO Loonland m.fl., Canada, 2000.    
    Produktion: TV 2|SPORTEN, 2010.
    Produktion: IWC Media, 2006, for Channel 4.
    Produktion: Nordisk Film, 2010, for TV 2¦Kommunikation.
    '''
    m = re.match(ur'^(.*?), (\d\d\d\d(?:-\d+)?).?$', rest)
    if m:
        g, y = m.groups()
    else:
        m = re.match(ur'^(.*?), (\d\d\d\d(?:-\d+)?),( for .*)?.?$', rest)
        if not m:
            return line
        g = m.group(1).strip() +' '+ m.group(3).strip()
        y = m.group(2)
        
    gs = re.split(ur'(?:,| for| &| og| i samarbejde med) ', g)
    for i in range(len(gs)):
        g = gs[i]
        for x in ['.','mfl','m.fl']:
            if g.endswith(x):
                g = g[:-len(x)].strip()
        gs[i] = g
    
    for y_ in y.split('-'):
        if y_.strip():
            prg.addTag('date', y_)
    for g in gs:
        if g.strip():
            prg.addTag('credit:producer', g.strip())
    return ''
addFilter(95, prefixFilter, ur"Produi?ktion:", fProduction)

def fEpisode(prg, line, prefix, rest):
    # Episode: 1:2
    # Episode: Del 1 av 9
    m = re.match(ur'(?:\(?|Del )(\d+)(?:(?::| av )(\d+))?\)?\.*', rest)
    if m:
        try:
            m0 = int(m.group(1))-1
            if m.group(2):
                m1 = int(m.group(2))
                txt = ".%d/%d." % (m0,m1)
            else:
                txt = ".%d." % m0
            prg.addTag('episode-num_system=xmltv_ns', txt)
            return ''
        except ValueError:
            pass
    return line
addPrefixFilter(ur'(?:Fortløbende|Originalt?|) ?[Ee]pisode(?:nr\.?|nummer|)\.?:?', fEpisode)

def fProgramcodes(prg, line, prefix, rest):
    # Programkoder: ((S)), Vises i bredformat.
    codes = rest.strip(".").split(",")
    remaining = []
    for code in codes:
        code = code.strip()
        if code:
            for (f, args) in _filters[20]:
                code = f(prg, code, *args)
                if not code:
                    break
            if code:
                remaining.append(code)
    if remaining:
        log('\nEXTRA Programcode: ' + repr(remaining) + '\n')
        return prefix + " " + ", ".join(remaining)
    else:
        return ''
addPrefixFilter(ur'Programkoder:', fProgramcodes)
            

def fExtras(prg, line, prefix, rest):
    if ':' in rest:
        return rest
    else:
        return line
addPrefixFilter(ur'Medvirkende:', fExtras)

def fOriginalTitle(prg, line, prefix, rest):
    prg.addTag('title_en', rest.strip('.'))
    return ''
addPrefixFilter(ur'Original ?tite?l?e?:', fOriginalTitle)

def fLength(prg, line, prefix, rest):
    'Længde: xxx min'
    m = re.match('(\d+) [mM]in\.?', rest)
    if m:
        prg.addTag('length_units=minutes', m.group(1))
        return ''
    return line
addPrefixFilter(ur"(?:Læn?gden?|Laufzeit):", fLength)

def fWWW(prg, line, prefix, rest):
    'www. ...'
    if prefix:
        url = prefix.rstrip(".").split()[-1]
        # log('LINE: %s --> URL: %s\n' % (line, url))
        prg.addTag('url', url)
        return rest.strip()
    return line
# Mere om aftenens program på www... ???
# Se flere nyheder på dr.dk/update
addPrefixFilter(ur'(?:Mere om aftenens program på |Se flere nyheder på |www\.)[^ ]+', fWWW)

def fPreviouslyShown(prg, line, prefix, rest):
    # Sendt første gang 26.01.10.
    if not re.match(ur"(?:[\d\. ]|og)+\.?$", rest):
        log('NO DATE MATCH: %s\n' % rest)
        return line

    dates = []
    for r in rest.split('og'):
        parts = [p for p in re.split(ur'[ .]+', r.strip()) if p]
        if len(parts) == 3:
            d,m,y = parts
        elif len(parts) == 2:
            d,m = parts
            y = None
        else:
            log('NO DATE MATCH: %s\n' % rest)
            return line
        d = d.zfill(2)
        m = m.zfill(2)
        if not y:
            y = str(time.localtime()[0])
            if prg['start'] < y+m+d:
                y = str(time.localtime()[0]-1) # last year
        try: 
            t = '.'.join((d,m,y))
            f = len(y) == 4 and '%Y' or '%y'
            t = time.strftime("%Y%m%d",time.strptime(t,"%d.%m."+f))
            dates.append(t)
        except ValueError, msg:
            if options.verbose:
                # sometimes we get illegal time stamps like 31.11
                sys.stderr.write("Unable to parse timestampe, %s: %s\n" % (t,msg))

    if not dates:
        return line
    
    for d in dates:
        prg.addTag('previously-shown_start='+d)
    return ''
addPrefixFilter(ur'Sendt førs(?:te|et) gang', fPreviouslyShown)
addFilter(10, splitByCreditPrefix, ur'Sendes også', False)
addFilter(10, splitByCreditPrefix, ur'Nordisk samproduktion|Nordvision', False)

DONE = '''
'''

TODO = '''Maybe also parse somethings like
  Dansk folkekomedie fra 1960.
    amr. komedieserie
    amr. dramaserie.
    Amerikansk thriller fra 1991.
    Engelsk krimi fra 1981.
    Israelsk prisbelønnet autentisk krigsdrama fra 2007.
    "Guldalderen"    (if on first line: a subtitle)
    Sendes også

Hvis : i titel og ingen sub-title, split!

if first line is repeated as the first part of the second line
if first line or subtitle is repeated later in (again)
o.w. if in (...), then is probably the origial title
first line with a dash:     - det er da ikke noget at skamme sig over! => subtitle

    Emma: Claire Holt, Cleo: Phoebe Tonkin og Rikki: Cariba Heine.
    Desuden medvirker: Lewis: Angus McLaren. Kim: Cleo Massey. Elliot: Trent Sullivan. Zane: Burgess Abernethy. Miriam: Anabelle Stephenson.


    Manuskript: Oliver Zahle, Jens Korse & Lotte Svendsen
    Max - Samuel Heller-Seiffert
    Mor - Mette Horn
    Far - Anders Nyborg
    Esther - Anna Agafia Svideniouk Egholm
    Steen Cold - Lars Bom
    Hassan - Faysal Mobahriz
    Ulla - Louise Mieritz

    Stuart Little: Michael J. Fox. (stemme)
    Snowbell: Nathan Lane. (stemme)
    Manuskript: M. Night Shyamalan og Greg Brooker efter E.B. Whites børnebog.
 
FIXIT
'''



# FIX

# pass 10 & 80
addCreditFilter("actor",       ur"Experte",      True)
addCreditFilter("actor",       ur"Jury",        True)
addCreditFilter("actor",       ur"Cast",        False)
addCreditFilter("actor",       ur"With",        False)
addCreditFilter("actor",       ur"Manuskript og medvirkende", False)

addCreditFilter("adapter",     ur"Animation",   True)
addCreditFilter("adapter",     ur"Foto(?:graf)?", True)
addCreditFilter("adapter",     ur"Kamera", True)
addCreditFilter("adapter",     ur"Regie", True)
addCreditFilter("adapter",     ur"Regissör", True)
addCreditFilter("adapter",     ur"Scenografi", True)
addCreditFilter("adapter",     ur"Screenplay", True)
addCreditFilter("adapter",     ur"Szenenbild", True)
addCreditFilter("adapter",     ur"(?:Signatur|Titel)?[Mm]usik", True)
addCreditFilter("adapter",     ur"Original Soundtrack", True)
addCreditFilter("adapter",     ur"Lydredigering", True)
addCreditFilter("adapter",     ur"Dansk version", True)
addCreditFilter("adapter",     ur"Koreografi", True)
addCreditFilter("adapter",     ur"Tilrettelæggelse", True)
addCreditFilter("adapter",     ur"TV ?2(?: Zulu| Charlie)?[- ]*[Rr]edakl?tør(?:er)?", True)
addCreditFilter("adapter",     ur"Moderation", True)

addCreditFilter("commentator", ur"Fortæller", True)
addCreditFilter("commentator", ur"Kommentator(?:er)?", False)
addCreditFilter("guest",       ur"Gæst(?:er)?", False)
addCreditFilter("presenter",   ur"Vært(?:er)?", False)
addCreditFilter("producer",    ur"Instruktion", True)
addCreditFilter("producer",    ur"Instruktion og tilrettelæggelse",   True)
addCreditFilter("producer",    ur"Instruktør", True)
addCreditFilter("producer",    ur"Directed by", False)
addCreditFilter("producer",    ur"Producere?", False)
addCreditFilter("producer",    ur"Produktion", False)
addCreditFilter("producer",    ur"Programleder", True)
addCreditFilter("producer",    ur"Distributør", True)

addCreditFilter("writer",      ur"Manus(?:kript)?", False)
addCreditFilter("writer",      ur"Manuskript og instruktion", False)
addCreditFilter("writer",      ur"Tekst", False)
addCreditFilter("writer",      ur"Buch", False)
addCreditFilter("writer",      ur"Drehbuch", False)
addCreditFilter("writer",      ur"Literarische Vorlage", False)

addCreditFilter("actor",       ur"Desuden medvirker",      False)
addCreditFilter("actor",       ur"Endvidere",      False)
addCreditFilter("actor",       ur"Medvirkende",      False)
addCreditFilter("actor",       ur"Medv\.",      False)
addCreditFilter("actor",       ur"Mitwirkende",      False)
addCreditFilter("actor",       ur"I rollene",      False)

addFilter(80, extractCredit, None, "actor", True)

# 100 and above also operate on the entire description
def removeDuplicates(prg, all):
    lines = all.split('\n')
    
    title = prg.getChild('title_da').text
    titles = [title]
    if ':' in title:
        titles.extend([t.strip() for t in title.split(":") if t.strip()])
    
    stitle = prg.hasChild('sub-title')
    if stitle:
        titles.append(stitle.text)

    titles.extend([u'(%s)' % t for t in titles] + 
                  [u'"%s"' % t for t in titles] + 
                  [u'(%s).' % t for t in titles] + 
                  [u'"%s".' % t for t in titles])

    for i in range(len(lines)):
        line = lines[i]
        if line in titles:
            lines[i] = u''

    if len(lines) >= 2 and lines[1].startswith(lines[0]):
        del lines[0]
        lines[0] = lines[0].lstrip(u'.').strip()

    if len(lines) >= 2:
        for i in range(len(lines)-1,0,-1):
            if lines[i] == lines[0]:
                del lines[i]
    
    lines = filter(None, lines)
    return '\n'.join(lines)        

addFilter(110, removeDuplicates)


# ---------- Hent Programmer for en specifik kanal og dag ---------- #

def getDayProgs(cid, day):
    data = readUrl(getDayURL(cid, day))[1]
    if not data:
        # log("[-No data available for day %s-]" % day)
        log(" :(")
        return []
    data = compact(data, True)
    trs = re.findall(r'<tr.*?</tr>',data)
    
    programmes = []
    realday = day
    for tr in trs:
        if '/info/' not in tr: continue
        prg = Programme('programme')
        prg['channel'] = cid

        # Extract time, pid and name
        # mre = re.search(u'<p>(\d\d):(\d\d):</p>.*<a[^>]*programid="([0-9]+)"[^>]*>([^<]+)</a>', tr)
        mre = re.search(u'<p>(\d\d):(\d\d):</p>.*<a[^>]*href="/info/([^"]+)"[^>]*>([^<]+)</a>', tr)
        if not mre:
            continue
        sh,sm, pid, title = mre.groups()
        if programmes and sh < programmes[-1].start[1]:
            # we are actually at the next day
            realday = day + 1
        prg.setTime('start', [realday,int(sh),int(sm),-1])
        prg.pid = pid
        prg.addTag('title_da',title)

        # some programmes have a category
        mre = re.search(u'/imgs/design/epg/types/[a-z]*.gif[^>]*pType="([^"]+)"',tr)
        if mre:
            prg.addTag('category', mre.group(1))
        else:
            category = None

        if programmes:
            programmes[-1].next = prg
        programmes.append(prg)

    if not programmes:
        # log("[-No data available for day %s-]" % day)
        log(" :o(")
        return

    # check for summer -> winter tz at 02:00 -> 02:59
    # this is detected when program i starts "after" program i+1
    for i in range(1,len(programmes)):
        pp, p = programmes[i-1:i+1]
        if int(pp.start[1]) == 2 and int(p.start[1]) == 2 and \
           int(pp.start[2]) > int(p.start[2]):
            # there must have been a tz change:
            # programmes[..i-1] is summer time, [i..] is winter time
            log("Summer to winter tz change detected\n")
            for j in range(len(programmes)):
                prg = programmes[j]
                tz = j < i and 1 or 0
                prg.setTime('start', prg.start[:-1] + [tz])
            break
        
    # Return the list of programmes found
    return programmes

def extendProgram(prg, forceRead = False):
    ''' Extend info about prg by using the special page for this particular program. This may return
    -1 : cache was used, but was unable to parse result - please retry!
    0  : cache was used - result may not be right
    1  : cache was not used - no need to run this again
    '''
    url = getProgrammeURL(prg.pid)
    cused, data = readUrl(url, forceRead)
    errcode = (cused and 1) or -1
    if not data:
        return errcode
    data = data
    
    ###########################

    # first delete ads
    data = re.sub(ur'<a[^>]+nofollow.*?>.*?</a>', '', data)
    # find blob with interesting data
    # and always skip the first <p>...</p>
    mpre = re.search('<td><h1>([^<]+)</h1><p>(?:[^<]+?)</p>', data)
    if not mpre:
        # nothing here!
        return errcode


    find_t = data.find('<table',mpre.end())
    find_td = data.find('</td>', mpre.end())
    find_p = data.find('</p>', mpre.end())

    if find_t < find_td:
        # we have the extended split-version of the page... :(
        # to get extended
        # find something like {'id':31263591900,'infoid':49076,'type':'movie'} in the html
        # and use http://ontv.dk/ajax/epg/cast.php?id=31263591900&infoid=49076&type=movie
        find_te = data.find('</table>',find_t)
        find_td = data.find('</td>', find_te)
        blob = data[mpre.end():find_t] + data[find_te+8:find_td]
    else:
        # we have the simple version of the page :)
        blob = data[mpre.end():find_td]

    if '<h3' in blob:
        # if available, this is the subtitle / or 'Om dette afsnit')
        m = re.compile('<h3.*?>(.*?)</h3>')
        sub = m.search(blob)
        if sub:
            # remove the first h3
            blob = m.sub('', blob, 1)
            sub = sub.group(1)
            # ignore 'Om dette afsnit' etc
            if sub.lower().startswith('om dette'):
                pass
            else:
                prg.addTag('sub-title_da',sub)

    
    blobs = slightlystripped(blob).split('\n')

    if blobs:
        # The first line is always something along the line of 
        # 'I morgen kl. 20.00 - 21.00 på DR1'
        # 'torsdag 21.01.2010 kl. 22.30 - 23:00 på DR2'
        if ' kl. ' in blobs[0]:
            m = re.search(r' kl. (\d?\d)[.:](\d\d) *- *(\d?\d)[.:](\d\d)', blobs[0])
            if m:
                sh,sm, eh, em = map(int, m.groups())

                prg.setTime('start', [prg.start[0], sh, sm, prg.start[-1]])

                day = sh <= eh and prg.start[0] or (prg.start[0]+1)
                if eh == 2 and prg.next:
                    tz = prg.next.start[-1]
                else:
                    tz = -1
                prg.setTime('stop', [day, eh, em, tz])
                del blobs[0]
    
    if blobs:
        addAllMetaData(prg, "\n".join(blobs))

    return 1

def getAll(cid, day):
    '''Get all programmes for channel cid on the particular day 
    '''

    programmes = getDayProgs(cid, day)
    if not programmes:
        log(' :( ')
        return

    for prg in programmes:
        oprg = copy.deepcopy(prg)

        r = extendProgram(prg, False)
        if r == 1:
            # no need to try further
            yield prg
            continue
        
        # cache was used, but program info may have changed
        if r == 0:
            okey = oprg['start'], oprg['title']
            key  = prg['start'], prog['title']
            if okey != key:
                # something is wrong we have to try again
                log("Flushing cached copy, since %s != %s\n" % (str(okey),str(key)))
                pass
            else:
                # no need to try again
                yield prg
                continue
        else:
            # could not parse file, try again
            pass

        # try again
        log('!--%s--' % prg.pid)
        r = extendProgram(oprg, True)
        yield oprg

def getChannelIcon(cid):
    '''Returns URL of channel logo'''
    url = getDayURL(cid, 2)
    data = readUrl(url)[1]
    if data: 
        data = data
        icons = re.findall('http://ontv.dk/imgs/epg/logos/[^\'"]+', data)
        if icons: 
            return icons[0]
    return None

# ---------- Spørg til konfigurationsfil ---------- #

if options.configure:
    # ensure that we can do Danish characters
    sys.stdout = codecs.getwriter(getNiceEncoding())(sys.stdout)
    folder = os.path.dirname(options.configfile)
    print u"The configuration will be saved in '%s'." % options.configfile
    if folder and not os.path.isdir(folder):
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
    for cid, name in parseChannels():
        answer = raw_input(u"Add channel %s (y/N) " % name).strip()
        if answer == "y":
            lines.append(u"channel %s %s\n" % (cid, name))
        else:
            lines.append(u"# channel %s %s\n" % (cid, name))
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

def outputChannels(channels):
    '''Given a list of (channelId, description) output info abouts channels'''
    for cid, channel in channels:
        print u"<channel id=\"%s\">" % cid 
        print u"    <display-name>%s</display-name>" % escape(channel)
        iconurl = getChannelIcon(cid)
        if iconurl:
            print "    <icon src=\"%s\"/>" % iconurl
        print "</channel>"

def outputXMLprefix():
    print u'<?xml version="1.0" encoding="UTF-8"?>'
    print u"<!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
    print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

def outputXMLpostfix():
    print u"</tv>"
    
if options.listchannels:
    outputXMLprefix()
    outputChannels(parseChannels())
    outputXMLpostfix()
    sys.exit(0)

log(sys.argv[0]+ '\n' + VERSION + '\n\n')
log("Generating list of channels: \n")
outputXMLprefix()
outputChannels(chosenChannels)

for cid, channel in chosenChannels:
    log("\n%s:"%channel)

    for day in range(options.offset, min(options.offset+options.days,maxdays)):
        log(" %d" % day)
        for programme in getAll(cid, day):
            print unicode(programme)
    
outputXMLpostfix()

log(u"\nDone.\n")
