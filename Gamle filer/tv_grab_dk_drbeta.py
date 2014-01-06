#!/usr/bin/env python
# -*- coding: utf-8 -*-
# $Id$
#
# Copyright (c) 2008, Jonas Häggqvist
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * Neither the name of the program nor the names of its contributors may be
#   used to endorse or promote products derived from this software without
#   specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# This grabber downloads data from the beta version of Danmarks Radio's new
# TV listing service using their JSON interface as defined here:
# http://beta.dr.dk/Programoversigt2008/DBService.ashx


from SimpleXMLWriter import SimpleXMLWriter
import sys
import json
import urllib
import urllib2
import re
import os
import datetime
import time
class drbetaReader:
    version = "0.1"
    channels = []
    channelinfo = {}
    __jsonurl = "http://beta.dr.dk/Programoversigt2008/DBService.ashx"
    __jsonid = 1
    __dateformat = "%Y%m%d%H%M%S %z"

    def __init__(self, config, verbose, output):
        self.config = config
        self.verbose = verbose
        self.output = output
        self.__nextdownload = datetime.datetime.now()

    def __output(self, string, verbose=True):
        if self.verbose or not verbose:
            print >> sys.stderr, (string)
        
    def fromISOdatetime(self, string):
        class SimpleTZ(datetime.tzinfo):
            def __init__(self, offset=0, name=""):
                if name == "":
                    name = "%+03d:%02d" % divmod(offset, 60)
                self.__name = name
                self.__offset = datetime.timedelta(minutes=offset)
            def utcoffset(self, dt):
                return self.__offset
            def tzname(self, dt):
                return self.__name
            def dst(self, dt):
                return datetime.timedelta()

        isoregexp = re.compile("""
        (?P<year>[0-9]{4})?-?       # Year
        (?P<month>[0-9]{2})?-?      # Month
        (?P<day>[0-9]{2})?          # Day
        T?
        (?P<hour>[0-9]{2})?:?       # Hour
        (?P<minute>[0-9]{2})?:?     # Minute
        (?P<second>[0-9]{2})?:?     # Second
        .?(?P<microsecond>[0-9]+)?  # Microsecond
        (?P<timezone>(?:Z|(?P<sign>[+-])(?P<tzhours>[0-9]{2})(?::?(?P<tzminutes>[0-9]{2}))?))? # Timezone
        """, re.VERBOSE)
        m = isoregexp.match(string)
        matches = m.groupdict(0)
        if matches["timezone"] != 0:
            if matches["timezone"] == "Z":
                offset = 0
            else:
                offset = 60*int(matches["tzhours"]) + int(matches["tzminutes"])
                if matches["sign"] == "-":
                    offset *= -1
            tz = SimpleTZ(offset, matches["timezone"])
        else:
            tz = None

        ret = datetime.datetime(
                int(matches["year"]),
                int(matches["month"]),
                int(matches["day"]),
                int(matches["hour"]),
                int(matches["minute"]),
                int(matches["second"]),
                int(matches["microsecond"]),
                tz
        )
        return ret

    def getListings(self, days=[1,]):
        self.doc = SimpleXMLWriter(self.output, indent=2)
        self.tv = self.doc.createElement("tv")
        self.tv.setAttribute("source-info-name", "DR.dk")
        self.tv.setAttribute("source-info-url", "http://beta.dr.dk/programoversigt2008/")
        self.tv.setAttribute("generator-info-name", "tv_grab_dk_drbeta/%s" % self.version)
        # self.doc.appendChild(self.tv)
        # Make sure we have the full channel info available
        if len(self.channelinfo) == 0:
            self.getChannelList()

        # Create channel elements at the top
        channels = []
        for channel in self.config.options("channels"):
            if self.config.get("channels", channel) == "on":
                channelinfo = self.channelinfo[channel]
                channels.append(channel)
                channelelm = self.doc.createElement("channel")
                channelelm.setAttribute("id", channel)

                # Get channelname from the config file so the user can change displayname easily
                if self.config.has_option("channelnames", channel):
                    channelname = self.config.get("channelnames", channel).decode("UTF-8")
                else:
                    channelname = channelinfo["name"].decode("UTF-8")
                # Remove the single letters denoting country in front of channelnames
                channelname = re.search("^(?P<countryletter>.:)?(?P<channelname>.*)", channelname).group("channelname")
                channelelm.appendChild(self.__elm("display-name", channelname))

                # Some channel define an URL for the channel's official website
                if "www_url" in channelinfo:
                    channelelm.appendChild(self.__elm("url", channelinfo["www_url"]))
                
                # icon_name is set if there's no icon for the channel
                if not "icon_name" in channelinfo:
                    iconname = os.path.basename(channel)
                    channelelm.appendChild(self.__elm("icon", "http://beta.dr.dk/Programoversigt2008/Images/Logos/%s.gif" % urllib.quote(iconname)))

                self.tv.appendChild(channelelm)


        dates = self.jsonCmd("availableBroadcastDates")
        today = self.jsonCmd("currentBroadcastDate")
        dates = dates[dates.index(today):dates.index(today)+len(days)]
        for date in dates:
            self.__output("Getting listings for %s:" % self.fromISOdatetime(date).strftime("%Y-%m-%d"))
            for channel in channels:
                schedule = self.jsonCmd("getSchedule", {"channel_source_url":channel, "broadcastDate":date})
                self.__output("  %s (%d programmes)" % (self.channelinfo[channel]["name"].decode("UTF-8"), len(schedule)))
                for programme in schedule:
                    ### Top-level element ###
                    pe = self.doc.createElement("programme")
                    pe.setAttribute("channel", channel)
                    if "pg_start" in programme:
                        pe.setAttribute("start", self.fromISOdatetime(programme["pg_start"]).strftime(self.__dateformat))
                    if "pg_stop" in programme:
                        pe.setAttribute("stop", self.fromISOdatetime(programme["pg_stop"]).strftime(self.__dateformat))

                    ### Title ###
                    # Do we use ppu_title or pro_title?
                    pe.appendChild(self.__elm("title", programme["pro_title"].decode("UTF-8")))
                    # Where does prd_series_title and pg_series_name fit in?
                    # Examples:
                    # 'prd_series_title':'Murder, She Wrote - s. 1+2 - eps. 1-43'
                    # 'pg_series_name': 'Hun så et mord'
                    # 'ppu_title_alt': 'Murder, She Wrote'
                    # 'ppu_punchline': 'Amerikansk krimiserie fra 1984.'

                    ### Repeat? ###
                    if programme["ppu_isrerun"]:
                        pe.appendChild(self.__elm("previously-shown"))

                    ### Video ###
                    # We always add the video element
                    video = self.__elm("video")
                    video.appendChild(self.__elm("present", "yes"))
                    if "ppu_video" in programme:
                        video.appendChild(self.__elm("aspect", programme["ppu_video"].decode("UTF-8")))
                    pe.appendChild(video)

                    ### Audio ###
                    # We always add the audio element
                    audio = self.__elm("audio")
                    audio.appendChild(self.__elm("present", "yes"))
                    if "ppu_audio" in programme:
                        if programme["ppu_audio"] in ("MONO", "STEREO", "SURROUND"):
                            val = programme["ppu_audio"].lower()
                        else:
                            val = programme["ppu_audio"]
                            print >> sys.stderr, ("Warning: unrecognised stereoness: %s" % val)
                        audio.appendChild(self.__elm("stereo", val))
                    pe.appendChild(audio)

                    ### Subtitle ###
                    # I'm not quite sure what the different values of this field mean
                    # TTV
                    # TTV_FOREIGN
                    # EXTERN
                    # FOREIGN
                    # NO_TXT
                    # Presumably all but the last means some subtitling is available 
                    if "ppu_subtext_type" in programme and programme["ppu_subtext_type"] != "NO_TXT":
                        subtitles = self.__elm("subtitles")
                        val = programme["ppu_subtext_type"]
                        if val == "TTV" or val == "TTV_FOREIGN":
                            type = "teletext"
                        else:
                            type = "onscreen"
                        subtitles.setAttribute("type", type)
                        pe.appendChild(subtitles)

                    ### Episode ###
                    if "prd_episode_number" in programme:
                        eps = self.__elm("episode-num")
                        eps.setAttribute("system", "onscreen")
                        self.doc.addText(str(programme["prd_episode_number"]))
                        pe.appendChild(eps)

                    ### Description ###
                    # This includes credits
                    if "ppu_description" in programme:
                        desc = programme["ppu_description"].decode("UTF-8")
                        pe.appendChild(self.__elm("desc", desc))

                    ### The rest ###
                    # These keys have a direct key -> element mapping
                    mapping = [
                            ("pro_category", "category"),
                            ("prd_genre_text", "category"),
                            ("ppu_www_url", "url"),
                            ("prd_prodcountry", "country"),
                            ]
                    for key, elm in mapping:
                        if key in programme:
                            val = programme[key].decode("UTF-8")
                            if elm == "url":
                                val = "http://" + val
                            pe.appendChild(self.__elm(elm, val))

                    ### All done ###
                    self.tv.appendChild(pe)
        self.doc.closeAll()

    # Convenience function that creates an element with an optional single text node as child
    def __elm(self, name, value = None):
        ret = self.doc.createElement(name)
        if value != None:
            self.doc.addText(value)
        return ret


    def getChannelList(self):
        channels = self.jsonCmd("getChannels", {"type":"tv"})
        for channel in channels:
            id   = channel["source_url"]
            name = channel["name"]
            self.channels.append((id, name))
            self.channelinfo[id] = channel
        self.channels.sort(cmp=lambda x,y: cmp(x[1].lower(), y[1].lower()))

    def jsonCmd(self, method, params = {}, retry = 0):
        if self.__nextdownload > datetime.datetime.now():
            diff = self.__nextdownload - datetime.datetime.now()
            secs = diff.microseconds/1000000.0 + diff.seconds + diff.days*24*3600
            time.sleep(secs)

        # We could use system.listMethods to check that cmd["method"]
        # is still recognised by the server?
        cmd = urllib.quote(json.JsonWriter().write({"id":self.__jsonid, "method":method, "params":params}))
        try:
            ret = json.read(urllib2.urlopen(self.__jsonurl, cmd).read())
            self.__nextdownload = datetime.datetime.now() + datetime.timedelta(seconds=self.config.getfloat("DEFAULT", "waitseconds"))
        except urllib2.URLError, e:
            # Retry on the following errors:
            # 104 - Connection reset
            # 110 - Connection timed out
            if e.reason[0] == 104 or e.reason[0] == 110:
                if retry < 5:
                    self.__output("%s - will retry in 5 seconds" % e.reason[1])
                    time.sleep(5)
                    return self.jsonCmd(method, params, retry + 1)
                else:
                    self.__output("%s - giving up" % e.reason[1])
            print >> sys.stderr, ("URL Error %d: %s (%s)" % (e.reason[0], e.reason[1], self.__jsonurl))
            sys.exit(3)
        # xxx: Check the ret["result"] and ret["id"] for sanity?
        if ret["id"] != self.__jsonid:
            print >> sys.stderr, ("JSON-RPC problem: ids don't match (%d vs %d)" % (ret["id"], self.__jsonid))
            sys.exit(4)
        self.__jsonid += 1
        return ret["result"]


import ConfigParser
def getConfig(configdir, configfile):
    # Build default config
    defaults = {"waitseconds":2.0}
    config = ConfigParser.SafeConfigParser(defaults)
    # Don't modify config keys (default is to lower-case them)
    config.optionxform = str

    # Create if it doesn't exist
    if not os.path.exists(configdir):
        os.makedirs(configdir)
    if not os.access(configfile, os.W_OK):
        try:
            config.write(open(configfile, 'wb'))
        except OSError:
            print >> sys.stderr, ("Can't create %s" % configfile)
            sys.exit(2)

    config.read(configfile)
    return config

def configureChannels(c, configfile):
    # Clear out channel settings
    c.config.remove_section("channels")
    c.config.remove_section("channelnames")
    c.config.add_section("channels")
    c.config.add_section("channelnames")

    c.getChannelList()

    for channel in c.channels:
        answer = raw_input(u"Add channel %s (y/N) " % (channel[1].decode("UTF8")))
        if answer.strip().startswith("y"):
            c.config.set("channels", channel[0], 'on')
        else:
            c.config.set("channels", channel[0], 'off')
        # Put the channel names in the config as a courtesy
        c.config.set("channelnames", channel[0], channel[1])

    c.config.write(open(configfile, 'wb'))


# Main function. This is where it all starts
import sys
import locale
import codecs
import encodings
import os
from optparse import OptionParser
def main(argv):
    # Set up stderr and stdout
    sys.stderr = codecs.getwriter(locale.getpreferredencoding())(sys.stderr)
    sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

    # Set up configuration - will create a default one if it doesn't exist
    grabbername = os.path.basename(sys.argv[0]).rstrip(".py")
    xmlcdir = os.path.expanduser("~/.xmltv/")
    defaultconffile = os.path.normpath(os.path.join(xmlcdir,grabbername + ".conf"))
    config = getConfig(xmlcdir, defaultconffile)

    # Figure out commandline options
    parser = OptionParser()
    parser.add_option("-v", "--verbose", dest="verbose", help="Be verbose", action="store_true", default=False)
    parser.add_option("-d", "--days", dest="days", help="Download this many days of listings. Defaults to 5.", metavar="DAYS", default="5")
    parser.add_option("-o", "--output", dest="output", help="Print xmltv output to OUTPUT. Use '-' for stdout (default)", metavar="OUTPUT", default="-")
    parser.add_option("-c", "--configure", dest="configure", help="Force reconfiguration of channels and exit", action="store_true", default=False)
    (options, args) = parser.parse_args(argv)

    if not options.days.isdigit():
        parser.print_help()
        print("\nError: Argument to --days must be an integer")
        sys.exit()

    # Create our reader instance
    if options.output == "-":
        output = sys.stdout
    else:
        output = open(options.output, 'w')
        output = codecs.getwriter("UTF-8")(output)
    c = drbetaReader(config, options.verbose, output)

    # Do channel configuration if requested, or no channels are defined
    if options.configure or not config.has_section("channels"):
        configureChannels(c, defaultconffile)
    # Otherwise, we get the tv listings
    else:
        c.getListings(days=range(1,int(options.days) + 1))


# run the main if we're not being imported:
import sys
if __name__ == "__main__":
    sys.exit(main(sys.argv))
