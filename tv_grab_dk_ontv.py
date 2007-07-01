#!/usr/bin/python
# -*- coding: UTF-8 -*-
#
# $Id$

import socket
socket.setdefaulttimeout(10)

# ---------- Lav kanal liste ---------- #
from urllib import urlopen
kanaldata = urlopen("http://ontv.dk/").read()
start = kanaldata.find('<div class="channels"')
end = kanaldata.find("<input", start)
import re
lande = re.findall(r'<div id="channels(\w\w)"(.*?)</div>', kanaldata[start:end], re.DOTALL)
kanalexpr = re.compile(r'<a href="/tv/(\d+)" style="font-weight:bold; font-family:Verdana; font-size:12px;">(.*?)</a>')
kanaler = []
for land, data in lande:
    landkanaler = kanalexpr.findall(data)
    for id, kanal in landkanaler:
        kanaler.append((id, "%s_%s"%(land,kanal)))

# ---------- Spørg til konfigurationsfil ---------- #
import os, sys
xmltvFolder = os.path.expanduser("~/.xmltv")
configureFile = os.path.expanduser("~/.xmltv/tv_grab_dk_ontv.conf")

if len(sys.argv) > 1 and sys.argv[1] == "--configure":
    if not os.path.exists(xmltvFolder):
        os.mkdir(xmltvFolder)
    if os.path.exists(configureFile):
        answer = raw_input("Konfigurationsfilen eksisterer allerede. Vil du overskrive den? (y/N) ").strip()
        if answer != "y":
            sys.exit()
    file = open(configureFile, "w")
    for id, name in kanaler:
        answer = raw_input("Tilføj %s (y/N) " % name).strip()
        if answer == "y":
            file.write("%s %s\n" % (id, name))
        else: file.write("#%s %s\n" % (id, name))
    sys.exit()

elif not os.path.exists(configureFile):
    print "Kan ikke finde configfile: %s" % configureFile
    sys.exit()

# ---------- Funktioner til parsing ---------- #

import time
def parseDay (day):
    t = time.time() + day*24*60*60
    date = time.strftime("%Y-%m-%d", time.gmtime(t))
    return date

def jumptime (days = 0, hours = 0, minutes = 0):
    t = [u for u in time.localtime()]
    t[3:9] = [0]*6
    t = time.mktime(t) + days*24*60*60 + hours*60*60 + minutes*60
    t += time.mktime(time.localtime()) - time.mktime(time.gmtime(time.time()))
    return time.gmtime(t)

cdataexpr = re.compile(r"<!\[CDATA\[([^<>]*)\]\]>")
retries = 3
def readUrl (url):
    for i in range (retries):
        try:
            data = urlopen(url).read()
            data = cdataexpr.sub(r"\1", data)
            return data
        except: pass
    return None

import htmlentitydefs
k = map(len,htmlentitydefs.entitydefs.keys())
ampexpr = re.compile("&(?![a-zA-Z0-9]{%d,%d};)" % (min(k),max(k)))

dayexpr = re.compile(r'(\d\d)[:.](\d\d):</p>(?:.*?)<a href="/programinfo/(\d+)">(.*?)\s*</a>')
progexpr = re.compile(r'(\d\d)[:.](\d\d) - (\d\d)[:.](\d\d)(?:(?:.*?)/serieinfo/(\d+)")*(?:(?:.*?)<p style="margin-top:0px;">(.*?)\s*</p>)*(?:(?:.*?)<img src="(/imgs/print_img.php?.*?)" alt="" />)*', re.DOTALL)
extraexpr = re.compile(r'<strong>(.*?):</strong>\s*(.*?)<')
starexpr = re.compile(r'<img src="http://ontv.dk/imgs/stjerne_(\w+)\.gif" />')
def getDayProgs (id, day):
    data = readUrl("http://ontv.dk/?s=tv&guide=&kanal=%s&date=%s" % (id, parseDay(day)))
    if not data:
        sys.stderr.write("\nIngen data for %s dag %s\n" % (id, day))
        yield []; return
    
    data = data.decode("iso-8859-1").encode("utf-8")
    start = data.find('<tr style="background-color:#eeeeee;">')
    end = data.find("</table>",start)
    
    programmes = dayexpr.findall(data, start, end)
    if not programmes:
        sys.stderr.write("\nIngen data for %s dag %s\n" % (id, day))
        yield []; return
    
    last = 0
    for sh, sm, info, title in programmes:
        if int(sh) < last: day += 1
        last = int(sh)
        
        for i in range (retries):
            data = readUrl("http://ontv.dk/programinfo/%s" % info)
            if not data:
                sys.stderr.write("\nTimeout for program %s\n" % info)
                yield parseSmallData(sh, sm, title, day)
                continue
                
            start = data.rfind('<div class="content"')
            end = data.find('class="titles">Brugernes mening',start)
            if end < 0: end = data.find("<iframe",start)
            data = data[start:end].decode("iso-8859-1").encode("utf-8")
            data = ampexpr.sub("&amp;",data)
            m = progexpr.search(data)
            
            if m: break

        if m == None:
            sys.stderr.write("\nMisdannet infomation for program %s\n" % info)
            yield parseSmallData(sh, sm, title, day)
        else:
            stars = starexpr.findall(data)
            extra = extraexpr.findall(data)
            yield parseData(title, stars, extra, m.groups(), day)

ampexpr = re.compile(r"&(?![\w#]+;)")
brexpr = re.compile(r"<\s*br\s*/\s*>", re.IGNORECASE)
def fixText (text):
    text = ampexpr.sub("&amp;",text)
    text = brexpr.sub("",text).strip()
    if text.endswith("."): text = text[:-1]
    return text

def parseData (title, stars, extras, groups, day):
    sh, sm, eh, em, link, info, img = groups
    dic = {}
    
    parseTitle(fixText(title), dic)
    if link: parseExtraLink(link, dic)
    if info: parseInfo(info, dic)
    if extras: parseExtras(extras, dic)
    if stars: parseStars(stars, dic)
    if img: dic["icon"] = "http://ontv.dk/"+img
    
    sh, sm, eh, em, day = map(int,(sh, sm, eh, em, day))
    dic["start"] = time.strftime("%Y%m%d%H%M%S", jumptime(day, sh, sm))
    tt = jumptime(day, eh, em)
    if eh < sh:
	time32 = time.mktime(tt)
	tt = time.gmtime(time32 + 3600 * 24 - time.timezone)
    dic["stop"] = time.strftime("%Y%m%d%H%M%S", tt)
   
    return dic

def parseSmallData (sh, sm, title, day):
    dic = {}
    parseTitle(fixText(title), dic)
    dic["start"] = time.strftime("%Y%m%d%H%M%S", jumptime(day, int(sh), int(sm)))
    return dic

maxStars = 10
def parseStars (stars, dic):
    noStars = 0
    for star in stars:
        if star == "fuld": noStars += 2
        elif star == "halv": noStars += 1
    if noStars > maxStars:
        sys.stderr.write(str(dic)+" \t"+str(stars))
    dic["stars"] = noStars

def parseExtraLink (link, dic):
    data = readUrl("http://ontv.dk/serieinfo/%s" % link)
    if not data: return
    start = data.rfind("</p><p>") + len("</p><p>")
    if start < 0 + len("</p><p>"):
        start = data.rfind("</h1><p>") + len("</h1><p>")
    if start < 0 + len("</h1><p>"):
        start = data.rfind("</table><p>") + len("</table><p>")
    if start < 0 + len("</table><p"):
        sys.stderr.write("Fejl i info :O")
        return
    end = data.find("</p>", start)
    data = data[start:end].decode("iso-8859-1").encode("utf-8")
    parseInfo(data, dic)

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
        sys.stderr.write("Titlen %s passer ikke til udtryk\n" % title)
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
        sys.stderr.write("Titlen %s passer ikke til simpeltudtryk\n" % title)
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

creditsDic = {"medvirk":"actor", "endvidere":"actor", "vært":"presenter", "manuskript":"writer", "instruktion":"director", "instruktør":"director", "foto":"adapter", "scenografi":"adapter", "signaturmusik":"adapter", "musik":"adapter", "kommentator":"commentator", "tekst":"adapter", "producer":"producer", "produktion":"producer", "tilrettelæggelse":"adapter", "gæst":"guest"}
dateexpr = re.compile(r' fra (\d\d\d\d)')
stripexpr  = re.compile(r'(:|,|og)\s*\r')
stripexpr2 = re.compile(r'\r\s*(:|,|og)')
timeexpr = re.compile(r'\.*(\d{1,2})\.+\s*(\d{1,2}|[a-zA-Z]+)\.*\s*(\d{1,4})?\.*')
monthdic = { "januar":"1", "jan":"1", "februar":"2", "marts":"3", "mar":"3", "april":"4", "apr":"4", "maj":"5", "juni":"6", "jun":"6", "juli":"7", "jul":"7", "august":"8", "aug":"8", "september":"9", "sep":"9", "oktober":"10", "okt":"10", "november":"11", "nov":"11", "december":"12", "dec":"12" }
def parseInfo (info, dic):
    info = fixText(info)
    isBad = lambda c: ord(c) < ord(" ") and c != "\n" and c != "\r"
    info = "".join([c for c in info if not isBad(c)])
    info = stripexpr.sub(r'\1 ', info)
    info = stripexpr2.sub(r' \1', info)
            
    normal = []
    for line in [l.strip() for l in info.splitlines()]:
        if not line: continue
        if line.startswith("Sendes også"):
            continue
        if line.startswith("Vises i bredformat"):
            dic["format"] = "2:1"
            continue
        if line[0] == "(" and (line[-1] == ")" or line.endswith(").")):
            simpleParseTitle(line[1:-1], dic)
            continue
        if line.startswith("Sendt første gang"):
            t = line[18:].strip()
            d, m, y = timeexpr.match(t).groups()
            if not m.isdigit(): m = monthdic[m]
            if m == None: raise AttributeError, "Bad month in %s" % t
            if y == None: y = time.strftime("%y")
            d, m, y = map(int, (d, m, y))
            y = ("%02d" % y)[-2:]
            t = ("%02d.%02d." % (d, m)) + y
            t = time.strftime("%Y%m%d",time.strptime(t,"%d.%m.%y"))
            dic["shown"] = t
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
            for char in person.decode("utf-8"):
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
    
    put ("descda", "\n".join(normal), dic)
    dic["descda"] = dic["descda"].replace("\n"," ")

def parseExtras (extras, dic):
    for key, value in [(k.lower(),fixText(v)) for k,v in extras]:
        if k == 'medvirkende':
            put("actor", splitPersons(value), dic)
        elif k == 'genre':
             dic["categoryda"] = value
        elif k == 'type' and not "categoryda" in dic:
            dic["categoryda"] = value
        elif k == 'fra':
            year, country = v.split(None,1)
            dic["date"] = year[:4]
            dic["country"] = country
        elif k == "episode":
            dic["episode"] = ".%s." % (str(af),str(ep))

def getChannelIcon (url):
    page = readUrl(url)
    if not page: return None
    s = len("<img src=\"")
    e = page.find("\"", s)
    return page[s:e]

# ---------- Læs fra konfigurationsfil ---------- #

chosenChannels = []
for line in open(configureFile, "r"):
    line = line.strip()
    if line and not line[0] == "#":
        chosenChannels.append(line.split(" ",1))
        
# ---------- Parse ---------- #

keyDic = {"titleda":"<title lang=\"da\">", "sub-titleda":"<sub-title lang=\"da\">", "title":"<title>", "sub-title":"<sub-title>", "categoryda":"<category lang=\"da\">", "descda":"<desc lang=\"da\">", "episode":"<episode-num system=\"xmltv_ns\">", "format":"<video><aspect>", "date":"<date>", "country":"<country>", "stars":"<star-rating><value>", "shown":"<previously-shown start=\"", "icon":"<icon src=\""}

endDic = {"titleda":"</title>", "sub-titleda":"</sub-title>", "title":"</title>", "sub-title":"</sub-title>", "categoryda":"</category>", "descda":"</desc>", "episode":"</episode-num>", "format":"</aspect></video>", "date":"</date>", "country":"</country>", "stars":"/%d</value></star-rating>" % maxStars, "shown":"\" />", "icon":"\" />"}

oneDic = {"utxt":"<subtitles type=\"teletext\" />",
"surround": "<audio><stereo>surround</stereo></audio>"}

credits = ("director", "actor", "writer", "adapter", "producer",
                   "presenter", "commentator", "guest")

sys.stderr.write("Parser: ")
print u"<?xml version=\"1.0\" ?><!DOCTYPE tv SYSTEM 'xmltv.dtd'>"
print u"<tv generator-info-name=\"XMLTV\" generator-info-url=\"http://membled.com/work/apps/xmltv/\">"

for id, channel in chosenChannels:
    sys.stderr.write("\n%s:"%channel)

    print "<channel id=\"%s\"><display-name>%s</display-name>" % (id, channel)
    iconurl = getChannelIcon("http://ontv.dk/extern/widget/kanalLogo.php?id=%s" % id)
    if iconurl: print "<icon src=\"%s\"/>" % iconurl
    print "</channel>"
    
    for day in range(15): #Går helt op til range(15)!!! (Vildt)
        sys.stderr.write(" %d" % day)
        for programme in getDayProgs(id, day):
            if not programme: continue
            print "<programme channel=\"%s\" start=\"%s\"" % (id, programme["start"])
            if "stop" in programme: print " stop=\"%s\"" % programme["stop"]
            print ">"
    
            for key, value in keyDic.iteritems():
                if programme.has_key(key):
                    print "%s%s%s" % (keyDic[key], programme[key], endDic[key])
        
            if len([c for c in credits if c in programme]) > 0:
                print "<credits>"
                for c in credits:
                    if programme.has_key(c):
                        for credit in programme[c]:
                            print "<%s>%s</%s>" % (c,credit,c)
                print "</credits>"

            for k, v in oneDic.iteritems():
                if k in programme:
                    print "%s" % v

            print "</programme>"
    
print "</tv>"

sys.stderr.write("\nFærdig...\n")
