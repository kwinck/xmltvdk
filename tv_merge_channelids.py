#! /usr/bin/env python
#  -*- coding: utf-8 -*-

VERSION = "$Id$"

'''
=pod

=head1 NAME

tv_merge_channelids - Merge multiple XMLTV channels into one

=head1 SYNOPSIS

tv_merge_channelids --help

tv_merge_channelids [options] -m CHANNELID [xmlfile]

=head1 DESCRIPTION

Merge XMLTV data for multiple channels into one. This is probably only
useful when multiple channels share a common frequency.

B<--help> Show available options and exit.

B<--quiet> Be very quiet. Only errors are printed to stderr.

B<--output>=I<FILENAME> File name of output xml file. If not provided
or -, stdout is used.

B<--mergedchannelid>=I<CHANNELID> XML channelid of the merged channel
(required).

B<--displayname NAME> Name of merged channel (default is to use the channelid).

B<--icon>=I<ICONURL> URL of icon for the merged channel.

B<--text>=I<TEXT> Text to use for title for programmes that are missing
some part. %(title)s is replaced with the original title. %(ostart)s
is replaced with the original starting time. %(ostop)s is replaced
with the original stopping time. Default: B<(%(title)s) Original:
%(ostart)s-%(ostop)s>.

B<--channel>=I<CHANNELID[@TIMESPAN,[TIMESPAN,[...]]]> XML channelid to
merge and corresponding timespan(s). If no timespans are specified,
the channel is merged in overlay mode (see EXAMPLES below). The most
simple form of a timespan is I<hh:mm-hh:mm> which specifies the
starting and stopping time (hour and minute) of the time span in local
time. A time span may cross midnight. This may be prepended with
weekday information using one of the forms w::hh:mm-hh:mm,
w-w::hh:mm-hh:mm, where w is a weekday number: Sunday is 0 and 7,
Monday is 1, Tuesday is 2, etc.

If not at least one B<--channel> options is used, the input is simply
passed to stdout.

=head1 EXAMPLES

I<TV2> shares the same frequency as I<TV2 Fyn>. Superimpose I<TV2 Fyn>
on top of TV2, i.e., whenever I<TV2 Fyn> has a program, show this. In
all other cases, show whatever is on I<TV2>:

  tv_merge_channelids.py -m tv2 -d "TV2 (Fyn)"
     -c tv2 -c tv2_fyn
     in.xml -o out.xml

I<Cartoon Network> and I<TCM> share the same frequency such that cartoon
network runs from 6:00 to 18:00, and I<TCM> from 18:00 to 6:00:

  tv_merge_channelids.py -m cartoon_tcm -d "Cartoon TCM" 
     -c tcm -c cartoon_network@6:00-18:00
     in.xml -o out.xml

which is equivalent to

  tv_merge_channelids.py -m cartoon_tcm -d "Cartoon TCM" 
     -c cartoon_network -c tcm@18:00-6:00
     in.xml -o out.xml

You can also make this depend on the weekday, i.e., as above but
Cartoon Network is only shown on weekdays:

  tv_merge_channelids.py -m cartoon_tcm -d "Cartoon TCM" 
     -c tcm -c cartoon_network@1-5::6:00-18:00
     in.xml -o out.xml

The above is equivalent to:

  tv_merge_channelids.py 
     -m cartoon_tcm -d "Cartoon TCM" 
     -c cartoon_network -c tcm@1-5::00:00-06:00,1-5::18:00-00:00
     in.xml -o out.xml

You can of course also merge more than two channels. 

=head1 SEE ALSO

L<xmltv(3pm)>.

=head1 AUTHOR

Jens Svalgaard Kohrt (http://svalgaard.net/jens/xmltv/). 

=head1 BUGS

Probably a lot. Check that you have the most recent version, and
contact the author.

=cut
'''

import calendar
import copy
import optparse
import re
import sys
import time

# match element(s) with a specific attribute
rElement = r'(?s)(<%s[^>]*%s="%s".*?</%s>[^<]*)' # % ("channel", "id", "tcm", "channel")

# find value of attribute in specific element
rAttValue = r'(?s)(<%s[^>]+%s=")([^"]*?)(")' # % ("programme", "start")

# legal time spans
rTimeSpan = r"^(([0-7])(-([0-7]))?::)?(0?\d|1\d|2[0123]):([0-5]?\d)-(0?\d|1\d|2[0123]):([0-5]?\d)$"

def replaceOrSetAttValue(tag, attribute, newValue, xml):
    # find previous value if available
    m = re.search(rAttValue%(tag,attribute),xml)
    if m:
        # replace
        return re.sub(rAttValue%(tag,attribute), 
                      lambda m: m.group(1) + newValue + m.group(3),
                      xml)
    else:
        # add
        return re.sub(r'(?s)(<%s[^>]*)(>)' % tag, 
                      lambda m: m.group(1)+' %s="%s"'%(attribute,newValue) + m.group(2),
                      xml)

def fixChannels(xml, conf):
    '''Fix channel information in xml by removing all channels that are to
    be merged and adding the new merged channel'''
    
    # find and remove all old channels
    reobsch = rElement % ("channel", 
                          "id", 
                          "(%s)" % "|".join(map(re.escape, conf["channelids"]+[conf["channelid"]])),
                          "channel")
    if conf["verbose"]:
        ochannels = [c[-1] for c in re.findall(reobsch, xml)]
        sys.stderr.write("Removing channelids to be merged: %s.\n" %
                         ", ".join(ochannels))
    xml = re.sub(reobsch, '', xml)
    
    # add our new channel
    if conf["verbose"]:
        ochannels = [c[-1] for c in re.findall(reobsch, xml)]
        sys.stderr.write("Adding new channel: %s (%s).\n" % (
            conf["channelid"],conf["displayname"]))
    newxml = '''<channel id="%s">
    <display-name>%s</display-name>%s
  </channel>
  ''' % (conf["channelid"],
         conf["channelid"],
         '\n    <icon src="%s" />' % conf["icon"] if "icon" in conf and conf["icon"] else "",
         )
    xml = re.sub("(?=<channel)",newxml,xml,1)
    
    return xml

def strftime(t):
    local = time.localtime(t)
    offset = -(time.altzone if local[-1] else time.timezone)
    offsets = "+" if offset >= 0 else "-"
    offsets += "%02d%02d" % (abs(offset) //3600, abs(offset)%3600)
    dt = time.strftime("%Y%m%d%H%M%S",local)  + " " + offsets
    return dt

def parseTimeStamp(s):
    '''Parse a xmltv time stamp. Returns None if the the time stamp does not 
    correspond to a recognized format: 
    20080726053000 +0200
    or 200807260530 +0200.'''
    p = s.strip().split(" ")
    if not (1 <= len(p) <= 2):
        return None
    try:
        f = "%Y%m%d%H%M" if len(p[0]) == 12 else "%Y%m%d%H%M%S"
        f += " %Z"
        
        res = calendar.timegm(time.strptime(p[0] + " GMT", f))
        if len(p) == 2:
            # we have tz data as well
            tz = int(p[1][1:])
            tzs = ((tz//100)*60+(tz%100))*60
            if p[0] == "+": res += tzs
            else: res -= tzs
        return res
    except ValueError:
        return None                

def parseProgramme(xmlp):
    '''parseProgramme(xmlp) -> dict containing information about the
    programme.'''
    res = {"xml" : xmlp}

    # find the channel
    m = re.search(rAttValue %("programme","channel"), xmlp)
    if not (m and m.group(2)):
        # according to XMLTV-DTD channel id must be there
        sys.stderr.write("Warning: ignoring program without channel id.\n")
        raise ValueError
    res["cid"] = m.group(2)
    
    # find the start time
    m = re.search(rAttValue %("programme","start"), xmlp)
    if not (m and m.group(2)):
        # according to XMLTV-DTD start time must be there
        sys.stderr.write("Warning: ignoring program without start time.\n")
        raise ValueError
    res["starto"] = m.group(2)
    res["start"] = parseTimeStamp(res["starto"])
    if not res["start"]:
        sys.stderr.write("Warning: ignoring program without start time.\n")
        raise ValueError

    # and the stop time (which may not be there)
    m = re.search(rAttValue %("programme","stop"), xmlp)
    if m and m.group(2):
        res["stopo"] = m.group(2)
        res["stop"] = parseTimeStamp(res["stopo"])
    else:
        res["stop"] = None

    # set edited flag. When writing xml and this is set to a true
    # value, the time stamp of this programme has been edited
    # somewhere. add "start"/"stop" to this to show that the
    # starting/stopping time has been altered.
    res["edited"] = set()

    return res

def parseTimeSpans(ts, first, last):
    '''Generate list of days from the day before first until a couple of
    days after last'''
    start = time.mktime(time.localtime(first)[:3] + (12,0,0,0,1,-1)) - 24*3600*2

    days = []
    for d in range(int(start), int(last)+3600*24*3,3600*24):
        d = time.localtime(d)
        days.append((d[:3], d[6]))
        
    res = []
    for t in ts:
        # t is in the format (possibly some parts missing)
        # 1-5::06:00-12:00 ('1-5::', '1', '-5', '5', '06', '00', '12', '00')

        m = re.match(rTimeSpan,t)
        # python week numbers are from 0 to 6, 0 is Monday
        if m.group(2):
            b = (int(m.group(2))-1)%7
            if m.group(4):
                # we have a range from e.g. 1 to 4
                e  = (int(m.group(4))-1)%7
                if b <= e:
                    wdays = set(range(b,e+1))
                else:
                    wdays = set(map(lambda x: x%7,range(b, e+1+7)))
            else:
                wdays = set([b])
        else:
            wdays = set(range(7))
            
        
        b = (int(m.group(5)), int(m.group(6)),0)
        e = (int(m.group(7)), int(m.group(8)),0)

        for i in range(len(days)-1):
            day, dayn = days[i:i+2]
            
            if day[1] in wdays:
                 # add this time span
                be = day[0] + b + (day[1], 0, -1)
                if b < e: # same day
                    en = day[0] + e + (day[1], 0, -1)
                else: # next day
                    en = dayn[0] + e + ((day[1]+1)%7, 0, -1)
                res.append((time.mktime(be), time.mktime(en)))

    # now skip timespans that are too early or late
    res = [r for r in res if first <= r[1] and r[0] <= last]
    
    return squeezeTimeSpans(res)

def squeezeTimeSpans(tss):
    tss.sort()
    if not tss:
        return []
    res = []
    cur = list(tss[0])
    for v in tss:
        if v[0] <= cur[1]:
            # this span overlaps the previous span
            cur[1] = max(cur[1], v[1])
        else:
            res.append(tuple(cur))
            cur = list(v)
    res.append(tuple(cur))
    return res        

def killByTimeSpan(prgs, tss):
    prgs.sort(key = lambda p: p["start"])
    tss = copy.deepcopy(tss)
    tss.sort()
    i = 0
    while i < len(prgs) and tss:
        p = prgs[i]
        # print p["cid"][:3], strftime(p["start"]), map(strftime,tss[0])
        if tss[0][1] <= p["start"]:
            del tss[0]
            continue
        ts = tss[0]
        if ts[0] <= p["start"]:
            if p["stop"] <= ts[1]:
                del prgs[i]
            else:
                p["start"] = ts[1]
                p["edited"].add("start")
        else:
            # span starts later than programme
            if p["stop"] <= ts[0]:
                # program is unaffected
                i += 1
            elif p["stop"] <= ts[1]:
                # cut the tail of our programme
                p["stop"] = ts[0]
                p["edited"].add("stop")
            else:
                # the time span cuts our programme in two
                pc = copy.deepcopy(p)
                p["stop"] = ts[0]
                p["edited"].add("stop")
                pc["start"] = ts[1]
                p["edited"].add("start")
                prgs.insert(i+1,pc)
                # i += 1 # TODO?
    # either no programs or time spans are left!

def reverseTimeSpans(tss):
    extra = 3600*24*365
    # find the reverse of the time spans given in tss
    res = [(tss[0][0]-extra,tss[0][0])]
    for i in range(len(tss)-1):
        res.append((tss[i][1], tss[i+1][0]))
    res.append((tss[-1][1], tss[-1][1]+extra))
    squeezeTimeSpans(res)
    return res

def fixXML(xml, conf):
    # first fix the channels
    xml = fixChannels(xml, conf)
    
    # now find all interesting programs and remove them from the xml
    prgs = dict([(id,[]) for id in conf["channelids"]])
    def prgScan(m):
        prg, id = m.groups()
        
        # get start/stop time etc
        d = parseProgramme(prg)
        prgs[id].append(d)
        return ""
    oxml = xml
    xml = re.sub(rElement % ("programme", 
                             "channel", 
                             "(%s)" % "|".join(map(re.escape, conf["channelids"])),
                             "programme"),
                 prgScan,
                 xml)
    if conf["verbose"]:
        sys.stderr.write("%d programmes removed from xml.\n" 
                         % sum([len(v) for v in prgs.values()]))

    # next ensure that all programmes (except possibly the last) have 
    # legal a stop time
    for vs in prgs.values():
        vs.sort(key = lambda x: x["start"])
        for i in range(len(vs)-1):
            v, vn = vs[i:i+2]
            if not v["stop"]:
                v["stop"] = vn["start"]
            elif v["stop"] > vn["start"]:
                v["stop"] = vn["start"]
            
    # now go though each channel and all the time spans
    result = []
    for i in range(len(conf["channelids"])):
        cid = conf["channelids"][i]
        ts = conf["timespans"][i]
        ps = copy.deepcopy(prgs[cid])
        if conf["verbose"]:
            sys.stderr.write("%s: %d programmes to consider.\n" % (cid, len(ps)))

        if (not result and not ps) or (ts=="overlay" and not ps):
            continue
        if ts == "overlay":
            if not result:
                result = ps
            else:
                # overlap all previous programs
                pss = [(p["start"], p["stop"]) for p in ps]
                if not pss[-1][1]:
                    # last stop time is missing - make this correspond to
                    # an 'infinite' stopping time
                    pss[-1] = (pss[-1][0], pss[-1][0]+265*24*3600)
                ts = squeezeTimeSpans(pss)
                killByTimeSpan(result, pss)
                result.extend(ps)
                result.sort(key = lambda x: x["start"])
        else:
            # find span of all programmes 
            stt = [result[0], result[-1]] if result else []
            stt += [ps[0], ps[-1]] if ps else []
            first = min([p["start"] for p in stt])
            last =  max([p["start"] for p in stt] + [p["stop"] for p in stt])
            # parse timespans
            ts = parseTimeSpans(ts, first, last)

            if ts:
                if conf["verbose"]:
                    for t in ts:
                        sys.stderr.write("\t%s -> %s\n" % tuple(map(strftime, t)))

                # kill all programmes within time span 
                killByTimeSpan(result, ts)

                # kill all programmes within current cid
                killByTimeSpan(ps, reverseTimeSpans(ts))
                result.extend(ps)
                result.sort(key = lambda x: x["start"])
            
    # now result is the list of programs we want to add to our xml

    # but first rewrite programs with missing parts
    result.sort(key = lambda x: x["start"])
    for p in result:
        pxml = p["xml"]
        
        # replace channelid
        pxml = replaceOrSetAttValue("programme", "channel", conf["channelid"], pxml)

        if p["edited"]:
            # add stuff to title
            ps = p["edited"]
            ostart = p["starto"].split(" ")[0][8:8+4]
            ostart = ostart[:2]+":"+ostart[2:]
            ostop = p["stopo"].split(" ")[0][8:8+4] if "stopo" in p else "????"
            ostop = ostop[:2]+":"+ostop[2:]
            
            def changeTitle(m):
                ntitle = conf["titletext"] % {
                    "ostart": ostart,
                    "ostop": ostop,
                    "title": m.group(2),
                    }
                res = m.group(1) + ntitle + m.group(3)
                return res
            pxml = re.sub(r'(?s)(<title[^>]*>)(.*?)(</title>)', changeTitle, pxml)
            
            # find new start time
            for tag in ["start", "stop"]:
                if tag in p["edited"]:
                    # replace start/stop time
                    pxml = replaceOrSetAttValue("programme", tag,
                                                strftime(p[tag]),
                                                pxml)
                    
                    # sys.exit(1)
            
        p["xml"] = pxml
    if conf["verbose"]:
        # print title and start time of all programmes in the merged channel
        sys.stderr.write("Result of merge:\n")
        for p in result:
            title = re.search(r'(?s)(<title[^>]*>)(.*?)(</title>)', p["xml"]).group(2)
            stime = strftime(p["start"])
            sys.stderr.write("\t%s %s %s\n" % (stime, p["cid"], title))

    # print result
    # add the results to the final xml again
    pxml = "".join([p["xml"] for p in result])
    tg = "</tv>"
    xml = xml.replace(tg,pxml + tg,1)
    
    if conf["verbose"]:
        sys.stderr.write("%d programmes added to xml.\n" % len(result))

    
    return xml    
        
def main():
    parser = optparse.OptionParser()

    parser.usage = "%prog [options] [xmlfile]"

    # general options
    parser.add_option("-q", "--quiet", dest="verbose", action="store_false",
                      default=True,
                      help="Be very quiet.")
    parser.add_option("-v", "--version", dest="version", action="store_true",
                      default=False,
                      help="Show version information and quit.")
    parser.add_option("-o","--output", dest="output", metavar="FILENAME",
                      default=None,
                      help=("File name of output xml file. If not provided "
                            "or '-', stdout is used."))

    # options re the merged channel
    parser.add_option("-m","--mergedchannelid", dest="channelid", metavar="CHANNELID",
                      default=None,
                      help="XML channelid of the merged channel (required).")
    parser.add_option("-d","--displayname", dest="displayname", metavar="NAME",
                      default=None,
                      help="Name of merged channel (default is to use the channelid).")
    parser.add_option("-i", "--icon", dest="icon", metavar="ICONURL",
                      default=None,
                      help="URL of icon for the merged channel.")
    tdef = "(%(title)s) Original: %(ostart)s-%(ostop)s"
    parser.add_option("-t", "--text", dest="titletext", metavar="TEXT",
                      default=tdef,
                      help=("Text to use for title for programmes that are "
                            "missing some part. "
                            "%%(title)s is replaced with the original title. "
                            "%%(ostart)s is replaced with the original starting time. "
                            "%%(ostop)s is replaced with the original stopping time. "
                            "Default: %s" % tdef))
                            

    # options re the channels to be merged
    parser.add_option("-c", "--channel", dest="channel", metavar="CHANNELID[@TIMESPAN,[TIMESPAN,[...]]]",
                      default=[], action="append",
                      help=("XML channelid to merge and corresponding "
                            "timespan(s). If no timespans are specified, " 
                            "the channel is merged in overlay mode (see "
                            "EXAMPLES below). The most simple form of a "
                            "timespan is I<hh:mm-hh:mm> which specifies the "
                            "starting and stopping time (hour and minute) of "
                            "the time span in local time. A time span may "
                            "cross midnight. This may be prepended with "
                            "weekday information using one of the forms "
                            "w::hh:mm-hh:mm, w-w::hh:mm-hh:mm, where w is a "
                            "weekday number: Sunday is 0 and 7, Monday is 1, "
                            "Tuesday is 2, etc."))
    
    options, args = parser.parse_args()
    if not options.displayname:
        options.displayname = options.channelid

    if options.version:
        print VERSION
        sys.exit(0)
    if not options.channelid: # required
        parser.error("Channelid '-m' is required")
    if len(args) > 1:
        parser.error("You can supply at most one input xml file")
        

    options.channelids = []
    options.timespans = []
    for ch in options.channel:
        och = ch
        
        if "@" not in ch:
            options.channelids.append(ch)
            options.timespans.append("overlay")
            continue

        m = re.match(r'^([^@]*)@(.+)$', ch)
        if not m:
            parser.error("Unable to parse -c option with channelid@timespan(s): %s" % och)
        cid = m.group(1)
        tss = m.group(2).split(",")

        for t in tss:
            m = re.match(rTimeSpan,t)
            if not m:
                # timespan is not parsable
                parser.error("Unable to parse timespan '%s' in: %s" % (t,och))

        options.channelids.append(cid)
        options.timespans.append(tss)


    # read input
    fd = open(args[0],"r") if args else sys.stdin
    xml = fd.read()
    
    if options.channelids:
        # if we actually have something to do
        conf = dict([(d,getattr(options,d)) for d in dir(options)])
        xml = fixXML(xml, conf)
    else:
        if options.verbose:
            sys.stderr.write("No channel timespans are defined - "
                             "simply passing input to output.")

    # write output
    fd = open(options.output,"w") if options.output else sys.stdout
    fd.write(xml)

if __name__ == "__main__":
    main()

