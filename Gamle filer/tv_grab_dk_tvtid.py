#!/usr/bin/python
# -*- coding: UTF-8 -*-
#
# This file contains an initial version of a tvtid-grabber
# it is not fully functional - but may use some nice ideas
# which can be used for other future grabbers.
#
# $Id$
#
# tv_grab_dk_tvtid v0.0.1
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

import sys
import urllib2
import os
import time
import re
import json
import datetime
import md5
from xml.dom.minidom import Document

class TvtidReader(object):
    _allChannels = {}
    _selectedChannels = {}
    _getDetails = ()
    _listings = {}
    _listingsurl = "http://tvtid.tv2.dk/js/fetch.js.php/from-%s.js"
    _detailsurl = "http://tvtid.tv2.dk/program/index.php/id-%s.html"
    _detailsRegexps = {
        'titleen':re.compile('<h. class="originalTitle">Originaltitel: ([^<]*)</h.>'),
        'episode':re.compile('<div class="episode">Episode: \(([^<]*)\)</div>'),
        'longdesc':re.compile('<div class="longinfo"><p>([^<]*)</p>'),
        'cast':re.compile('<h2 class="programListHeader">Medvirkende:</h2><p>([^<]*)</p>'),

        'format43':re.compile('class="pictureFormat43 (enabled|disabled)"'),
        'format169':re.compile('class="pictureFormat169 (enabled|disabled)"'),
        'rerun':re.compile('class="rerun (enabled|disabled)"'),
        'surround':re.compile('class="surround (enabled|disabled)"'),
        'teletext':re.compile('class="teletext (enabled|disabled)"'),
        'subtitles':re.compile('class="subtitles (enabled|disabled)"'),
        'blackwhite':re.compile('class="blackwhite (enabled|disabled)"'),
        'subtitlesHearingImpaired':re.compile('class="subtitlesHearingImpaired (enabled|disabled)"'),
    }
    throttle = datetime.timedelta(0,10)
    _nextTime = datetime.datetime.now() - datetime.timedelta(0,5)

    def getChannelList(self):
        """
        Get the full list of channels available and store them internally
        This is done by downloading the listing for the next midnight
        """
        # Next midnight - should be sure to exist
        timestamp = (datetime.date.today() + datetime.timedelta(1)).strftime('%s')
        url = self._listingsurl % timestamp

        data = self._getURL(url)
        object = json.read(data)
        for channel in object['channels']:
            self._allChannels[str(channel['id'])] = channel['name'].encode("UTF-8")

        #xxx: hardcoded
        self._selectedChannels = self._allChannels.fromkeys(['11825154','11823880','11826003'])
        self._getDetails = self._allChannels.fromkeys(['11825154'])
        for id in self._selectedChannels:
            self._selectedChannels[id] = self._allChannels[id]

    def printSelectedChannels(self):
        """
        Print all selected channels
        """
        self._printChannelList(self._selectedChannels)

    def printAllChannels(self):
        """
        Print all available channels
        """
        self._printChannelList(self._allList)

    def _printChannelList(self, list):
        """
        Print a given list of channels.
        """
        for id in list:
            print "%s (%d)" % (list[id], id)

    def getListings(self, start, end):
        """
        Get all listings from start to end - both must be datetime objects
        and at least start must be a time where the hours are divisible by
        zero, and minutes, seconds and milliseconds set to 0.
        """
        # Set up empty listings
        self._listings = {}
        for id in self._selectedChannels:
            self._listings[id] = []

        # Loop from start to end, adding 4 hours each time
        while start <= end:
            timestamp = start.strftime('%s')
            url = self._listingsurl % timestamp

            data = self._getURL(url)
            object = json.read(data)

            for channel in object['channels']:
                # Only look after selected channels
                channelid = str(channel['id'])
                if self._listings.has_key(channelid):
                    for program in channel['program']:
                        # Only get details for specified channels
                        if self._getDetails.has_key(channelid):
                            program.update(self.getDetails(program['program_id']))
                            pass
                        self._listings[channelid].append(program)

            #start += datetime.timedelta(800)

            start += datetime.timedelta(0,0,0,0,0,4)

    def printListings(self):
        """
        Print listings in human readable (ish) form
        """
        for channelid in self._listings:
            print("Channel: %s" % self._selectedChannels[channelid])
            for program in self._listings[channelid]:
                print "%s - %s: %s" % (program['start'],program['end'],program['title'])
                if program.has_key('longdesc'):
                    print "               - %s" % program['longdesc']
                if program['short_description'] != "":
                    print "               - %s" % program['short_description']
            print ""

    def getDetails(self, id):
        """
        Get the details of a specific program. This imethod performs an awful
        lot of regexp matching. Probably not the best choice performance-wise
        """
        url = self._detailsurl % id
        ret = {}
        data = self._getURL(url)
        for key in self._detailsRegexps:
            match = self._detailsRegexps[key].search(data)
            if match != None:
                ret[key] = match.group(1).decode("Latin-1")
        return ret

    def _getURL(self, URL):
        """
        Return the content of an URL, while keeping track of not overloading
        the server.
        """
        storefile = md5.new(URL).hexdigest()
        try:
            return open(storefile).read()
        except IOError:
            while self._nextTime > datetime.datetime.now():
                print "Waiting until %s to download %s" % (self._nextTime.isoformat(' '), URL)
                time.sleep(1)
            opener = urllib2.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            # use temp variable so we can reset the time *after* the transfer
            # is done (or slow transfers might mean we never waited)
            data = opener.open(URL).read()
            print "Getting %s" % URL
            self._nextTime = datetime.datetime.now() + self.throttle
            try:
                f = file(storefile, 'w')
                f.write(data)
                f.close()
            except IOError:
                pass
            return data

    def printXMLTV(self):
        """
        Output the currently downloaded listings as an XMLTV file
        """
        doc = Document()
        tv = doc.createElement("tv")
        tv.setAttribute("source-info-name", "http://tvtid.dk")
        tv.setAttribute("generator-info-name", "tv_grab_dk_tvtid/0.1")
        doc.appendChild(tv)

        for channelid in self._listings:
            channel = doc.createElement("channel")
            channel.setAttribute("id", channelid)
            displayname = doc.createElement("display-name")
            displayname.appendChild(doc.createTextNode(self._selectedChannels[channelid]))
            channel.appendChild(displayname)
            tv.appendChild(channel)

        for channelid in self._listings:
            for p in self._listings[channelid]:
                programme = doc.createElement("programme")
                programme.setAttribute("channel", channelid)
                # xxx: timezone
                programme.setAttribute("start", datetime.datetime.fromtimestamp(p['start_timestamp']).strftime("%Y%m%d%H%M%S"))
                programme.setAttribute("stop", datetime.datetime.fromtimestamp(p['end_timestamp']).strftime("%Y%m%d%H%M%S"))

                title = doc.createElement("title")
                title.appendChild(doc.createTextNode(p['title']))
                programme.appendChild(title)
                
                if p['short_description'] != "":
                    subtitle = doc.createElement("sub-title")
                    subtitle.appendChild(doc.createTextNode(p['short_description']))
                    programme.appendChild(subtitle)

                if p.has_key('longdesc'):
                    desc = doc.createElement("desc")
                    desc.appendChild(doc.createTextNode(p['longdesc']))
                    programme.appendChild(desc)

                tv.appendChild(programme)
        print doc.toprettyxml(indent="  ")

def main(argv):
    c = TvtidReader()
    c.getChannelList()
    days = 0 # Read this many days in addition to today
    # Yikes
    start = datetime.datetime.today().replace(hour=0,minute=0,second=0,microsecond=0)
    end = start + datetime.timedelta(days, 0, 0, 0, 0, 20)

    c.getListings(start, end)
    #c.printListings()
    c.printXMLTV()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
