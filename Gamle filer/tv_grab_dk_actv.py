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
# The ACTV website is not a particular nice source for TV listings for a
# couple of reasons:
# 1) A lot of channels listed actually don't contain any data
# 2) It only has listings a few days ahead of time
# 3) It has short descriptions, if any
# 
# I made this grabber anyway because:
# 1) It's fast, needing only to download a single page
# 2) It has episode numbers and fairly good information about repeats,
#    subtitling etc.
# 3) Because it's there.

import datetime
import urllib2
import md5
import sys
import time
class throttlingcachingdownloader:

    def __init__(self, cachedir=".", throttle = 10, verbose=False):
        self.cachedir = cachedir
        self.throttle = throttle
        self._nextTime = datetime.datetime.now() - datetime.timedelta(0,throttle)
        self.verbose = verbose

    def getURL(self, URL):
        """
        Return the content of an URL, while keeping track of not overloading
        the server.
        """
        storefile = "%s/tcd_cache_%s" % (self.cachedir, md5.new(URL).hexdigest())
        try:
            return open(storefile).read()
        except IOError:
            if self.verbose:
                print >> sys.stderr, ("Cache miss")
            if self._nextTime > datetime.datetime.now():
                sleep = (self._nextTime - datetime.datetime.now()).seconds
                if self.verbose:
                    print >> sys.stderr, ("  Waiting until %s to download %s (sleeping %d seconds)" % (self._nextTime.isoformat(' '), URL, sleep))
                time.sleep(sleep)
            opener = urllib2.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            # use temp variable so we can reset the time *after* the transfer
            # is done (or slow transfers might mean we never waited)
            data = opener.open(URL).read()
            if self.verbose:
                print >> sys.stderr, ("  Getting %s" % URL)
            self._nextTime = datetime.datetime.now() + datetime.timedelta(0,self.throttle)
            try:
                f = file(storefile, 'w')
                f.write(data)
                f.close()
            except IOError:
                pass
            return data


from BeautifulSoup import BeautifulSoup
from xml.dom.minidom import Document
import sys
import re
import pytz
class actvReader:
    version = "0.1"
    channels = []
    _channelgroups = []

    def __init__(self, config, verbose):
        self.config = config
        self.d = throttlingcachingdownloader(cachedir=config.get("DEFAULT", "cachedir"), throttle = config.getint("DEFAULT", "waitseconds"), verbose=verbose)
        self.doc = Document()
        self.tv = self.doc.createElement("tv")
        self.tv.setAttribute("source-info-name", "Allers tv-redaktion")
        self.tv.setAttribute("source-info-url", "http://actv.dk/")
        self.tv.setAttribute("generator-info-name", "tv_grab_dk_actv/%s" % self.version)
        self.doc.appendChild(self.tv)
        self.verbose = verbose

    def _output(self, string, verbose=True):
        if self.verbose or not verbose:
            print >> sys.stderr, (string)

    def getListings(self, days=[1,]):
        urlf = "http://www.actv.dk/perl/tvdata.pl?produkt=SH&dag=%d&kanal=%s&tid=1&omtale=1#%s"
        # The URL we get is of the following form:
        # http://www.actv.dk/perl/tvdata.pl?produkt=SH&dag=1&kanal=004&tid=1&omtale=1
        # produkt - Select one of actv's output schemes (SH and BB)
        # dag     - Which day to show listings for. 1 means today, 2 means tomorrow, etc
        # kanal   - Which channels to show. May be a comma separated list of channel ids
        # tid     - What timeframe to show. 1=All day, 2=Rest of the day, 3=Right now
        # omtale  - Whether or not to show long descriptions
        #
        # This script only varies for dag and kanal. We append the date to the
        # URI to make sure caching works out right.

        episodere = re.compile(" \((?P<episode>(?P<episodeno>[0-9\+]+)(:(?P<episodecount>[0-9]+))?)\)$")
        cph_tz = pytz.timezone("Europe/Copenhagen")
        for day in days:
            self._output("Getting listings for day %d" % day, False)

            channels = []
            channelnames = []
            channelnametoid = {}
            for channel in self.config.options("channels"):
                if self.config.get("channels", channel) == 'on':
                    channelname = self.config.get("channelnames", channel)
                    channels.append(channel)
                    channelnames.append(channelname)
                    channelnametoid[channelname] = channel

                    # Add channel elements to the xmltv output
                    channelelm = self.doc.createElement("channel")
                    channelelm.setAttribute("id", channel)
                    displayname = self.doc.createElement("display-name")
                    displayname.appendChild(self.doc.createTextNode(channelname))
                    channelelm.appendChild(displayname)
                    self.tv.appendChild(channelelm)

            self._output("  Channels: " + ", ".join(channelnames))

            url = urlf % (day, ",".join(channels), datetime.datetime.now().strftime("%Y%m%d"))
            self._output("  URL: %s" % url)
            data = self.d.getURL(url)
            soup = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
            trs = soup.body.findAll("table")[0].findAll("tr",recursive=False)
            if len(trs) < 3:
                continue
            rowtype = "startname"
            for row in trs[1:]:
                if rowtype == "startname":
                    spans = row.findAll("span")
                    start_s = row.findAll("p")[0].contents[-1]
                    start_t = datetime.time(int(start_s.split(".")[0]), int(start_s.split(".")[1]), tzinfo=cph_tz)
                    start = datetime.datetime.combine(
                            datetime.date.today(),
                            start_t
                    )
                    # Add a day if time between 00:00 and 05:00
                    if start_t < datetime.time(5, tzinfo=cph_tz):
                        start += datetime.timedelta(days=1)

                    category = spans[2].string

                    programme = self.doc.createElement("programme")

                    # If we're only grabbing one channel, it won't be printed
                    # in the HTML, so use the channelname we set earlier
                    if not len(channels) == 1:
                        channelname = spans[1].contents[-1].strip()
                    programme.setAttribute("channel", channelnametoid[channelname])
                    programme.setAttribute("start", start.strftime("%Y%m%d%H%M%S %z"))

                    title = self.doc.createElement("title")
                    titletext = row.findAll("a")[0].string.strip()
                    # Check for episode numbers
                    episode = episodere.search(titletext)
                    if episode != None:
                        episodenum = self.doc.createElement("episode-num")
                        episodenum.setAttribute("system", "onscreen")
                        # Just copy the episode string verbatim. Alternatively,
                        # episode.group("episodeno") and
                        # episode.group("episodecount") can be used to create a
                        # nicer episode string
                        episodenum.appendChild(self.doc.createTextNode(episode.group("episode")))
                        programme.appendChild(episodenum)
                        titletext = episodere.sub("", titletext)
                    title.appendChild(self.doc.createTextNode(titletext))
                    programme.appendChild(title)

                    # Always create a video element for simplicity
                    video = self.doc.createElement("video")
                    present = self.doc.createElement("present")
                    present.appendChild(self.doc.createTextNode("yes"))
                    video.appendChild(present)

                    for img in spans[1].findAll("img"):
                        if img["title"] == u"Genudsendelse":
                            ps = self.doc.createElement("previously-shown")
                            programme.appendChild(ps)
                        elif img["title"] == u"Tekstet":
                            st = self.doc.createElement("subtitles")
                            st.setAttribute("type", "onscreen")
                            programme.appendChild(st)
                        elif img["title"] == u"Tekstet på tekst-tv":
                            st = self.doc.createElement("subtitles")
                            st.setAttribute("type", "teletext")
                        elif img["title"] == u"16:9 format":
                            aspect = self.doc.createElement("aspect")
                            aspect.appendChild(self.doc.createTextNode("16:9"))
                            video.appendChild(aspect)
                        elif img["title"] == u"Sort/Hvid":
                            colour = self.doc.createElement("colour")
                            colour.appendChild(self.doc.createTextNode("no"))
                            video.appendChild(colour)
                        elif img["title"] == u"Premiere":
                            premiere = self.doc.createElement("premiere")
                            programme.appendChild(premiere)
                        else:
                            self._output("Script warning, unknown programme information: %s" % (img["title"]))

                    programme.appendChild(video)

                    # See if there's a category for this programme
                    category = spans[2].string.strip()
                    if category != u"--":
                        cat = self.doc.createElement("category")
                        cat.appendChild(self.doc.createTextNode(category))
                        programme.appendChild(cat)

                    rowtype = "desc"
                elif rowtype == "desc":
                    tds = row.findAll("td")
                    duration_m = tds[0].contents[0]
                    stop = start + datetime.timedelta(minutes=int(duration_m))
                    programme.setAttribute("stop", stop.strftime("%Y%m%d%H%M%S %z"))

                    programme.setAttribute("showview", tds[1].i.string)

                    if tds[1].span.string != None:
                        desc = self.doc.createElement("desc")
                        desc.appendChild(self.doc.createTextNode(tds[1].span.string))
                        programme.appendChild(desc)

                    self.tv.appendChild(programme)
                    rowtype = "startname"

    def getChannelList(self, grouppage=1):
        urlf = "http://www.actv.dk/perl/tvchooser.pl?produkt=SH&kanaler=%d"
        # http://www.actv.dk/perl/tvchooser.pl?produkt=SH&kanaler=1
        url = urlf % (grouppage)
        if grouppage in self._channelgroups:
            return False
        self._channelgroups.append(grouppage)
        self._output("Get channel list %d" % grouppage)
        self._output("  URL: %s" % url)
        data = self.d.getURL(url)
        soup = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
        for option in soup.find("select", attrs={"name" : "kanal"}).findAll("option")[1:]:
            name = option.string.strip()

            # The channel list doesn't quite match what used in the listings
            namereplacements = [
                ("TV1000", "TV 1000"),
                ("3+", "TV3+"),
                ("TV Danmark", "Kanal 4"),
                ("Nat. Geographic", "National Geographic"),
                ("TV 3 Norge", "TV3 Norge"),
                ("TV 2 Norge", "TV2Norge"),
                ("NRK 1", "NRK1"),
                ("TV 4 Sverige", "Sverige TV4"),
                ("TV 3 Sverige", "TV3 Sverige"),
                ("TV 2 Sverige", "Sverige TV2"),
                ("TV 1 Sverige", "Sverige TV1"),
                ("TV 3", "TV3 Danmark") # Keep this one last
            ]
            for (orig, replace) in namereplacements:
                name = name.replace(orig, replace)
            id = re.search("kanal=([0-9]+)", option["value"]).group(1)
            self.channels.append((id, name))
        for option in soup.find("select", attrs={"name":"kanaler"}).findAll("option"):
            group = int(re.search("kanaler=([0-9]+)", option["value"]).group(1))
            if group not in self._channelgroups and option.string.strip() != "Radio":
                self.getChannelList(group)
        # Sort channels at the end of it all
        if grouppage == 1:
            self.channels.sort(cmp=lambda x,y: cmp(x[1].lower(), y[1].lower()))

import ConfigParser
def getConfig(configdir, configfile):
    # Build default config
    defaults = {"cachedir":configdir,"waitseconds":5}
    config = ConfigParser.ConfigParser(defaults)

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
        answer = raw_input(u"Add channel %s (y/N) " % (channel[1]))
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
    c = actvReader(config, options.verbose)

    # Do channel configuration if requested, or no channels are defined
    if options.configure or not config.has_section("channels"):
        configureChannels(c, defaultconffile)
    # Otherwise, we get the tv listings
    else:
        c.getListings(days=range(1,int(options.days) + 1))
        if options.output == "-":
            c.doc.writexml(sys.stdout, addindent="  ", newl="\n")
        else:
            output = open(options.output, 'w')
            output = codecs.getwriter("UTF-8")(output)
            c.doc.writexml(output, addindent="  ", newl="\n")


# run the main if we're not being imported:
import sys
if __name__ == "__main__":
    sys.exit(main(sys.argv))
