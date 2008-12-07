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


from xml.dom.minidom import Document
import sys
import json
import urllib
import urllib2
class drbetaReader:
    version = "0.1"
    channels = []
    jsonurl = "http://beta.dr.dk/Programoversigt2008/DBService.ashx"
    _channelgroups = []
    _jsonid = 1

    def __init__(self, config, verbose):
        self.config = config
        self.doc = Document()
        self.tv = self.doc.createElement("tv")
        self.tv.setAttribute("source-info-name", "DR.dk")
        self.tv.setAttribute("source-info-url", "http://beta.dr.dk/programoversigt2008/")
        self.tv.setAttribute("generator-info-name", "tv_grab_dk_drbeta/%s" % self.version)
        self.doc.appendChild(self.tv)
        self.verbose = verbose

    def _output(self, string, verbose=True):
        if self.verbose or not verbose:
            print >> sys.stderr, (string)

    def getListings(self, days=[1,]):
        # Create channel elements at the top
        channels = []
        for channel in self.config.options("channels"):
            if self.config.get("channels", channel) == "on":
                channels.append(channel)
                channelelm = self.doc.createElement("channel")
                channelelm.setAttribute("id", channel)
                if self.config.has_option("channelnames", channel):
                    channelname = self.config.get("channelnames", channel).decode("UTF-8")
                    displayname = self.doc.createElement("display-name")
                    displayname.appendChild(self.doc.createTextNode(channelname))
                    channelelm.appendChild(displayname)
                self.tv.appendChild(channelelm)
                pass

        dates = self.jsonCmd("availableBroadcastDates")
        for daynum in days:
            date = dates["result"][daynum - 1]
            for channel in channels:
                schedule = self.jsonCmd("getSchedule", {"channel_source_url":channel, "broadcastDate":date})
                for programme in schedule["result"]:
                    pe = self.doc.createElement("programme")
                    pe.setAttribute("channel", channel)
                    pe.setAttribute("start", programme["pg_start"])
                    pe.setAttribute("stop", programme["pg_stop"])
                    title = self.doc.createElement("title")
                    title.appendChild(self.doc.createTextNode(programme["ppu_title"].decode("UTF-8")))
                    pe.appendChild(title)
                    self.tv.appendChild(pe)
                    pass


    def getChannelList(self):
        channels = self.jsonCmd("getChannels", {"type":"tv"})
        for channel in channels["result"]:
            id   = channel["source_url"]
            name = channel["name"]
            self.channels.append((id, name))
        self.channels.sort(cmp=lambda x,y: cmp(x[1].lower(), y[1].lower()))

    def jsonCmd(self, method, params = {}):
        # We could use system.listMethods to check that cmd["method"]
        # is still recognised by the server?
        cmd = urllib.quote(json.JsonWriter().write({"id":self._jsonid, "method":method, "params":params}))
        ret = json.read(urllib2.urlopen(self.jsonurl, cmd).read())
        # xxx: Check the ret["result"] and ret["id"] for sanity?
        self._jsonid += 1
        return ret


import ConfigParser
def getConfig(configdir, configfile):
    # Build default config
    defaults = {"cachedir":configdir,"waitseconds":5}
    config = ConfigParser.SafeConfigParser(defaults)

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
    c = drbetaReader(config, options.verbose)

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
