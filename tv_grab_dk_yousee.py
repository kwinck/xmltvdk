#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# $Id$


# Copyright by Jesper Saxtorph <sax.xmltv@manware.dk>
# This code is supplied as is with no warrenty at all.
# Use it at your own risk.
# You are permitted to do whatever you like with it as long as you leave
# this copyright notice.

# This means if you add your own code or change this, just add your own name.
# If you make a copyright notice for your own code different from the above,
# please be specific about what code you have added/changed.


# TODO
# - make it follow the recomendations from xmltv: http://wiki.xmltv.org/index.php/XmltvCapabilities
#     Capability "manualconfig" refers to a perl library - is this necessary?
#     GUI config missing
#     API config missing
# - Handling of screwed up guide data from YouSee
# - Usage information (pytz, ...)
# - Do not add times for missing end times - leave it to user app.
# - Check time arithmetic according to http://pytz.sourceforge.net/ (normalize)
# - Split and merge channel programmes as used by YouSee cable net
# - More complete handling of unexpected webpage layout
# - More complete error handling
# - Code comments

import cookielib
import urllib2
import datetime
import codecs
import locale
import sys
import re
import htmlentitydefs
import time

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
	import pytz
except ImportError:
	class PyTZ:
		def timezone(self, tzstring):
			return LocalTimeZone()
	pytz = PyTZ()

def get_file_revision():
	rev_key=u'$Rev: 121 $'
	return rev_key[6:-2]

# Snatched from http://kofoto.rosdahl.net/trac/wiki/UnicodeInPython
def get_file_encoding(f):
	if hasattr(f, "encoding") and f.encoding:
		return f.encoding
	else:
		return locale.getpreferredencoding()
# End of snatch


##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.
#
# Written by Fredrik Lundh
# Taken from http://effbot.org/zone/re-sub.htm#unescape-html
# Modified to not unescape special chars & < >
# Also added convertion of lone & to &amp; as yousee use that sometimes.
def html_unescape(text):
	def fixup(m):
		text = m.group(0)
		if text[:2] == "&#":
			# character reference
			try:
				if text[:3] == "&#x":
					newtext = unichr(int(text[3:-1], 16))
				else:
					newtext = unichr(int(text[2:-1]))
				if not (newtext in [ u'&', u'>', u'<' ]):
					text = newtext
			except ValueError:
				pass
		else:
			# named entity
			try:
				if not text[1:-1] in [ u'amp', u'gt', u'lt']:
					text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
			except KeyError:
				pass
		return text # leave as is
	def remove_amps(m):
		return u'&amp;'
	return re.sub(u'&(?!#?\w+;)', remove_amps, re.sub(u'&#?\w+;', fixup, text))


class BaseTVGrabber:
	
	def __init__(self):
		
		self.statusOk = 0
		self.errorNoArgs = -1
		self.errorWrongArgMix = -2
		self.errorNotIntArg = -3
		self.errorOutOfRange = -4
		self.warningOutOfRange = 4
		self.errorCouldNotOpenOutput = -5
		self.errorUnknownArgument = -6
		
		home = os.path.expanduser('~')
		if home == '~':
			sys.stderr.write("Could not determine your home directory - Using root as base\n")
			home = ''
		self.xmltvDir = home + '/.xmltv'
		
		# Standard values - overwrite in specialized grabber
		self.progname = u'Unnamed XMLTV grabber'
		self.version = u'Unknown'
		self.description = u'Unknown'
		self.capabilities = []
		self.defaultConfigFile = self.xmltvDir + '/grabber.conf'
		self.configFile = None
		
		# Standard values for some parameters
		self.quiet = False
		self.configure = False
		self.listchannels = False
		self.gui = False
		self.offset = 0
		self.days = None
		self.output = None
		
		self.outputEncoding = 'utf-8'
		# Danish timezone
		self.dktz = pytz.timezone('Europe/Copenhagen')
		self.timeformat = '%Y%m%d%H%M %z'
	
	def setQuiet(self, quiet):
		self.quiet = quiet
	
	def setOutputEncoding(self, outputEncoding):
		self.outputEncoding = outputEncoding
	
	def parseNextArgument(self, argv, argnum):
		# In this function
		# positive status values coresponds to the number of arguments found
		
		if len(argv) == 0: status = self.errorNoArgs
		else: status = 1
		if status > 0:
			arg = argv.pop(0)
			if arg == '--capabilities':
				for capability in self.capabilities:
					print capability
				if (len(argv) > 0) or (argnum > 1):
					sys.stderr.write("--capabilities should be used alone\n")
					status = self.errorWrongArgMix
				else:
					sys.exit(0)
			elif arg == '--version':
				print self.progname, u'version', self.version
				if (len(argv) > 0) or (argnum > 1):
					sys.stderr.write("--version should be used alone\n")
					status = self.errorWrongArgMix
				else:
					sys.exit(0)
			elif arg == '--description':
				print self.description
				if (len(argv) > 0) or (argnum > 1):
					sys.stderr.write("--description should be used alone\n")
					status = self.errorWrongArgMix
				else:
					sys.exit(0)
			elif arg == '--help':
				if (len(argv) > 0) or (argnum > 1):
					sys.stderr.write("--help should be used alone\n")
					status = self.errorWrongArgMix
				else:
					self.printUsage()
					sys.exit(0)
			elif arg == '--quiet':
				self.quiet = True
			elif arg == '--configure':
				self.configure = True
			elif arg == '--list-channels':
				self.listchannels = True
			#elif arg == '--gui':
			#	self.gui = True
			elif len(argv) > 0:
				status += 1
				val = argv.pop(0)
				if arg == '--config-file':
					self.configFile = val
				elif arg == '--offset':
					try:
						self.offset = int(val)
					except:
						status = self.errorNotIntArg
						sys.stderr.write("The offset given is not an integer\n")
					if self.offset < 0:
						self.offset = 0
						status = self.errorOutOfRange
						sys.stderr.write("The offset given should be a positive number\n")
				elif arg == '--days':
					try:
						self.days = int(val)
					except:
						status = self.errorNotIntArg
						sys.stderr.write("The number of days given is not an integer\n")
					if self.days < 1:
						self.days = 1
						status = self.errorOutOfRange
						sys.stderr.write("The number of days given should be at least 1\n")
				elif arg == '--output':
					self.output = val
				else:
					# reinsert arguments
					argv.insert(0, val)
					argv.insert(0, arg)
					status = 0
			else:
				# reinsert arguments
				argv.insert(0, arg)
				status = 0
		return status
	
	def printUsage(self):
		sys.stderr.write("Usage:\n")
		sys.stderr.write(" --help\n")
		sys.stderr.write("     Give this information (should be the only argument)\n")
		sys.stderr.write(" --description\n")
		sys.stderr.write("     Give a ultra short description of the grabber\n")
		sys.stderr.write(" --capabilities\n")
		sys.stderr.write("     List standard xmltv capabilities (should be the only argument)\n")
		sys.stderr.write(" --version\n")
		sys.stderr.write("     Give the version (should be the only argument)\n")
		sys.stderr.write(" --quiet\n")
		sys.stderr.write("     Supress as many messages as possible\n")
		sys.stderr.write(" --configure\n")
		sys.stderr.write("     Configure the grabber\n")
		#sys.stderr.write(" --gui\n")
		#sys.stderr.write("     Indicate a wish for graphical information/questions (not supported yet)\n")
		sys.stderr.write(" --config-file <filename>\n")
		sys.stderr.write("     Configuration file to use\n")
		sys.stderr.write('     Default is "'+self.defaultConfigFile+'"\n')
		sys.stderr.write(" --offset <offset>\n")
		sys.stderr.write("     Day to start grabing on. 1 means tomorrow.\n")
		sys.stderr.write(" --days <days>\n")
		sys.stderr.write("     Number of days to grab\n")
		sys.stderr.write(" --output <filename>\n")
		sys.stderr.write("     A file to put the programme in instead of stdout\n")
	
	def checkSetup(self):
		# Overwrite this in grabbers to test e.g. days is set lower than what can be fetched
		return self.statusOk
	
	def parseArguments(self, argv):
		# Strip command name
		argv = argv[1:]
		status = 1
		argnum = 0
		while (len(argv) > 0) and status > 0:
			argnum += 1
			status = self.parseNextArgument(argv, argnum)
		if status < 0:
			sys.stderr.write("Error in arguments given\n")
			self.printUsage()
		elif len(argv) > 0:
			sys.stderr.write('Unknown argument "'+argv[0]+'"\n')
			self.printUsage()
			status = self.errorUnknownArgument
		else:
			status = self.statusOk
		return status
	
	def splitTitle(self, title):
		# Check for empty input
		if not title: return u'', u''
		# Split up
		titles = title.split(u': ',1)
		if len(titles) == 1:
			titles = title.split(u' - ',1)
		if len(titles) == 1:
			return title.strip(), u''
		else:
			return titles[0].strip(), titles[1].strip()
	
	def splitDescription(self, title, desc):
		# Check for empty input
		if not desc: return u'', u''
		# Check if we start with "
		# this will normally indicate a subtitle
		if desc[0] == u'"':
			# Split up
			res = desc[1:].split(u'". ',1)
			if len(res) < 2:
				return u'', desc
			elif res[0].find(u'"') >= 0:
				return u'', desc
			elif title == res[0]:
				return u'', desc
			else:
				return res[0], res[1]
		else:
			return u'', desc
	
	def splitPersons(self, persons):
		# Check for empty input
		if not persons: return []
		# Split up
		personlist = persons.split(u',')
		last = personlist[-1].split(u' og ', 1)
		if len(last) > 1:
			personlist[-1] = last[0]
			personlist.append(last[1])
		# Strip whitespace from names
		for index in range(len(personlist)):
			personlist[index] = personlist[index].strip()
		# Remove empty elements
		found = True
		while found:
			try:
				personlist.remove('')
			except:
				found = False
		# Drop trailing '.'
		if personlist[-1][-1] == u'.':
			personlist[-1] = personlist[-1][:-1]
		return personlist
	
	def cleanChannelId(self, indata):
		legal  = u'abcdefghijklmnopqrstuvwxyz'
		legal += legal.upper()
		legal += u'0123456789'
		legal += u'-.'
		if indata[0] == u'.': outdata = u'dot'
		else: outdata = u''
		for index in range(len(indata)):
			if indata[index] in legal:
				outdata += indata[index]
			elif indata[index] in u'_ ':
				outdata += u'-'
			elif indata[index] in u'%&':
				outdata += u'And'
			elif indata[index] in u'+':
				outdata += u'Plus'
			else:
				try:
					value = ord(indata[index])
					outdata += u'-' + hex(value) + u'-'
				except:
					sys.stderr.write("Could not use char: %s\n" % indata[index])
		return outdata


class YouSeeGrabber(BaseTVGrabber):
	
	def __init__(self, initSession=False, developerInfo=False):
		BaseTVGrabber.__init__(self)
		
		self.progname = u'tv_grab_dk_yousee'
		self.version = get_file_revision()
		self.description = u'Denmark (yousee.tv/tvguide)'
		self.capabilities = ['baseline', 'manualconfig']
		self.defaultConfigFile = self.xmltvDir + '/tv_grab_dk_yousee.conf'
		self.configFile = self.defaultConfigFile
		
		self.offset = 0
		self.maxDays = 7
		self.days = self.maxDays
		
		self.developerInfo = developerInfo
		self.weekDay = {u'mand':1,u'tirs':2,u'onsd':3,u'tors':4,u'fred':5,u'lørd':6,u'sønd':7}
		self.daynames = [u'idag', u'imorgen', u'iovermorgen', u'omtredage', u'omfiredage', u'omfemdage', u'omseksdage']
		self.startDay = datetime.date.today()
		self.today = self.startDay
		self.pageLoadTries = 3
		self.channels = []
		self.programme = {}
		self.retrieveDetails = True
		# (title+ , sub-title* , desc* , credits? , date? , category* , language? , orig-language? , length? , icon* , url* , country* , episode-num* , video? , audio? , previously-shown? , premiere? , last-chance? , new? , subtitles* , rating* , star-rating?)
		self.infoMap = {'id':0,'start':1,'stop':2,'title':3,'actors':4,'desc':5,'director':6,'sub-title':7,'video-format':8, 'stereo':9,'previously-shown':10,'subtitles':11}
		self.webPageEncoding = 'utf-8'
		self.opener = None
		self.forcedEncoding = False
		
		if initSession:
			self.newSession()
	
	def printUsage(self):
		BaseTVGrabber.printUsage(self)
		sys.stderr.write(" --list-channels\n")
		sys.stderr.write("     List available channels. The list is in xmltv-format\n")
		sys.stderr.write(" --no-details\n")
		sys.stderr.write("     Drop details thereby making it a lot faster\n")
		sys.stderr.write(" --output-encoding\n")
		sys.stderr.write("     Output encoding to use (defaults to utf-8)\n")
		
	def parseNextArgument(self, argv, argnum):
		status = BaseTVGrabber.parseNextArgument(self, argv, argnum)
		if status == 0:
			arg = argv.pop(0)
			if arg == '--no-details':
				self.retrieveDetails = False
			elif len(argv) > 0:
				status += 1
				val = argv.pop(0)
				if arg == '--output-encoding':
					self.outputEncoding = val
					self.forcedEncoding = True
				else:
					# reinsert arguments
					argv.insert(0, val)
					argv.insert(0, arg)
					status = 0
			else:
				# reinsert arguments
				argv.insert(0, arg)
				status = 0
		return status
	
	def checkSetup(self):
		status = self.statusOk
		if self.offset >= self.maxDays:
			status = self.warningOutOfRange
			sys.stderr.write("The guide only hold data for "+str(self.maxDays)+" days\n")
		elif self.offset + self.days > self.maxDays:
			self.days = self.maxDays - self.offset
			status = self.warningOutOfRange
			sys.stderr.write("The guide only hold data for "+str(self.maxDays)+" days\n")
		return status
	
	def getWebPage(self, url, retries=None):
		if not self.opener: self.newSession()
		if not retries: retries = self.pageLoadTries
		page = None
		while (retries > 0) and not page:
			try:
				pageHandle = self.opener.open(url)
				page = pageHandle.read()
				page = unicode(page, self.webPageEncoding)
			except KeyboardInterrupt:
				sys.stderr.write("Program interrupted\n")
				sys.exit(1)
			except:
				retries -= 1
		return page
	
	def newSession(self, day=None):
		cj = cookielib.CookieJar()
		self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
	
	def cleanForURL(self, indata):
		outdata = ''
		for index in range(len(indata)):
			if (not indata[index].isalnum()) or indata[index] in [u'æ', u'ø', u'å', u'Æ', u'Ø', u'Å']:
				try:
					code = '%'
					value = ord(indata[index])
					if value < 16:
						code += '0'
					code += hex(value)[2:].upper()
					outdata += code
				except:
					sys.stderr.write("Could not use char: %s\n" % indata[index])
			else:
				outdata += indata[index]
		return outdata
	
	def extractElement (self, data, index, name):
		index = data.find(name, index)
		if index == -1: return None
		index = data.find(u'value', index)
		if index == -1: return None
		index = data.find(u'=', index)
		if index == -1: return None
		index = data.find(u'"', index) + 1
		if index == -1: return None
		index2 = data.find(u'"', index)
		if index2 == -1: return None
		value = data[index:index2]
		return value

	def extractChannels (self, data):
		index = data.find(u'<select name="channel">', 0)
		# First channel option is "alle" meaning all and is therefore skipped
		index = data.find(u'</option>', index) + len(u'</option>')
		index2 = data.find(u'</select>', index)
		while index < index2:
			channelUrl = self.extractElement(data, index, u'option')
			if channelUrl:
				channel, index = self.extractNextProgrammeDetail(data, index, u'>', u'</option>')
				if channel and index < index2:
					xmltvId = self.cleanChannelId(channelUrl+u'.yousee.dk')
					while xmltvId in [xi for c,cu,a,xi in self.channels]:
						xmltvId += '-X'
					self.channels.append( (channel, channelUrl, False, xmltvId) )
				else:
					sys.stderr.write("Problem parsing for channels")
					index = index2
			else:
				index = index2
	
	def retrieveChannels (self):
		self.channels = []
		
		if not self.quiet: sys.stderr.write("Retrieving channels\n")
		url = 'http://yousee.tv/tvguide/alle/idag'
		data = self.getWebPage(url, 10)
		if data:
			self.extractChannels (data)
		else:
			sys.stderr.write("Could not get channels")
	
	def getChannels (self):
		return self.channels
	
	def loadChannels (self, filename):
		loadLocals = {}
		try:
			execfile(filename, globals(), loadLocals)
			try:
				version = int(loadLocals['version'])
			except ValueError:
				version = 0
			if (version < 121):
				sys.stderr.write("Warning: You should update %s by deleting the old and make a new\n" % filename)
				sys.stderr.write("Sorry for the inconvienence\n")
				return False
			self.channels = loadLocals['channels']
			return True
		except:
			return False
	
	def saveChannels (self, filename):
		try:
			output = codecs.open(filename, 'w', 'utf-8')
		except:
			return False
		succes = True
		try:
			output.write(u'#!/usr/bin/env python\n')
			output.write(u'# -*- coding: utf-8 -*-\n')
			output.write(u'\n')
			output.write(u"progname  = u'"+self.progname  +u"'\n")
			output.write(u"version   = u'"+self.version   +u"'\n")
			output.write(u'\n')
			output.write(u'# If you edit this file by hand, only change active and xmltvid columns.\n')
			output.write(u'# (channel, channelUrl, active, xmltvid)\n')
			output.write(u'channels = [\n')
			for ch in self.channels:
				output.write(str(ch) + u',\n')
			output.write(u']\n')
		except:
			sys.stderr.write("Could not save channels!\n")
			succes = False
		output.close()
		return succes
	
	def extractDaySeven (self, data):
		index = data.find(u'selectTimeAction')
		if index >= 0:
			index = data.find(u'value="7"', index)
			if index >= 0:
				index += len(u'value="7">')
				dayString = data[index:index + 4]
				if dayString == u'sele':
					index += len(u'selected>')
					dayString = data[index:index + 4]
				day = self.weekDay[dayString.lower()]
				return day
		return None
	
	def extractNextProgrammeDetail (self, data, index, before, after, strip=True):
		index1 = data.find(before, index)
		if index1 == -1: return (None, index)
		else: index1 += len(before)
		index2 = data.find(after, index1)
		if index2 == -1: return (None, index)
		value = data[index1:index2]
		if strip: value = self.stripHTMLSpecials(value.strip())
		return (value, index2 + len(after))
	
	def makeProgrammeInfoList(self, progid, start=None, stop=None, title=None, actors=None, desc=None, director=None, format=None, sound=None, prevshown=None, subtitles=None):
		info = [None]*len(self.infoMap)
		info[self.infoMap['id']] = progid
		info[self.infoMap['start']] = start
		info[self.infoMap['stop']] = stop
		info[self.infoMap['title']], info[self.infoMap['sub-title']] = self.splitTitle(title)
		info[self.infoMap['actors']] = self.splitPersons(actors)
		if info[self.infoMap['sub-title']]:
			info[self.infoMap['desc']] = desc
		else:
			info[self.infoMap['sub-title']], info[self.infoMap['desc']] = self.splitDescription(info[self.infoMap['title']], desc)
		info[self.infoMap['director']] = self.splitPersons(director)
		info[self.infoMap['video-format']] = format
		info[self.infoMap['stereo']] = sound
		info[self.infoMap['previously-shown']] = prevshown
		info[self.infoMap['subtitles']] = subtitles
		return info
	
	def extractBaseProgramme(self, data):
		programme = []
		# Run through every programme section
		index = 0
		# Skip until the programme comes
		index = data.find(u'<div class="content">', index)
		while index >= 0:
			# This string indicates a programme section start
			index = data.find(u'<dt>', index)
			if index != -1:
				index2 = data.find(u'</dd>', index)
				# Get the programme id
				programmeId, index = self.extractNextProgrammeDetail(data, index, u'showprograminfo(', u');')
				if programmeId:
					title, index = self.extractNextProgrammeDetail(data, index, u'">', u'</a>')
					if index >= index2: title = None
					start, index = self.extractNextProgrammeDetail(data, index, u'Kl. ', u' -')
					if index >= index2: start = None
					stop,  index = self.extractNextProgrammeDetail(data, index, u' ', u'</a>')
					if index >= index2: stop = None
					programme.append(self.makeProgrammeInfoList(progid=programmeId, start=start, stop=stop, title=title))
				index = index2
		return programme
	
	def retrieveBaseDayProgramme(self, channel, channelUrl, day):
		# TODO fix handling of dayshift
		baseProgramme = []
		# fetch the page with the base programme (no details)
		url = u'http://yousee.tv/tvguide/kanal/'+self.cleanForURL(channelUrl)+u'/'+self.daynames[day]
		data = self.getWebPage(url, 10)
		if data:
			# Check the week day and thereby set the date
			#guideDate = self.extractGuideDate (data)
			#if not guideDate:
			#	sys.stderr.write("Could not find the day!\n")
			#	return None
			#if guideDate != self.today.isoweekday(): # TODO
			#	# The day has changed
			#	self.today += datetime.timedelta(1)
			#	if guideDate != self.today.isoweekday():
			#		# Something is wrong the day has changed, but not to the next!
			#		sys.stderr.write("Error with days!\n")
			#		return None
			# Parse the base programme
			baseProgramme = self.extractBaseProgramme(data)
		else:
			sys.stderr.write("Could not get programme for %s\n" % channel)
		return baseProgramme
	
	def stripHTMLSpecials (self, data):
		# convert all numeric and named entities to utf-8 chars
		data = html_unescape(data)
		# replace '& ' with '&amp; '
		#data = data.replace(u'& ', u'&amp; ')
		# remove all '<br />'
		data = data.replace(u'<br />', u' ')
		# remove all '&nbsp;'
		#data = data.replace(u'&nbsp;', u' ')
		
		return data
	
	def makeTime (self, timeStr, relativeDay):
		# You always have two digits for minutes, so find it from behind
		try:
			hour = int(timeStr[0:-3])
			minute = int(timeStr[-2:])
		except:
			sys.stderr.write("Could not convert %s\n" % timeStr)
			return None
		date = self.today + datetime.timedelta(relativeDay)
		try:
			time = datetime.time(hour, minute)
		except:
			sys.stderr.write("Could not convert %s\n" % timeStr)
			return None
		return datetime.datetime.combine(date, time)
	
	def extractProgrammeDetails (self, data, progid):
		index = 0
		subdata, index = self.extractNextProgrammeDetail(data, index, u'<div class="properties">', u'\t</div>')
		# extract:
		# <div>TTV</div>, <div>(G)</div>, <div>16:9</div>
		# between index and index2
		format = None
		prevshown = None
		subtitles = None
		sound = None
		detail, index2 = self.extractNextProgrammeDetail(subdata, 0, u'<div>', u'</div>')
		while detail:
			if detail:
				if detail == u'16:9':
					format = detail
				elif detail == u'(G)':
					prevshown = True
				elif detail == u'TTV':
					subtitles = u'teletext'
				elif detail == u'((S))':
					sound = u'surround'
				elif detail == u'S':
					# Not sure what this is? Mono?
					dummy = None
				elif detail == u'SH':
					# Not sure what this is? Black & White?
					dummy = None
				elif detail == u'TH':
					# Tekstet for hørehæmmede: is this special subtitles or hand sign?
					dummy = None
				elif detail == u'T':
					# Not sure what this is? onscreen subtitles?
					dummy = None
				elif detail == u'5:1':
					# What the heck is this?
					dummy = None
				else:
					if not self.quiet:
						sys.stderr.write("Got unknown detail: '%s'" % detail)
						sys.stderr.write(" for programme '%s'\n" % progid)
				detail, index2 = self.extractNextProgrammeDetail(subdata, index2, u'<div>', u'</div>')
		
		# Skip title and time as we already have that
		subdata, index = self.extractNextProgrammeDetail(data, index, u'<p>', u'/p>')
		title = None
		start = None
		stop = None
		# Find the start of the description
		desc, index = self.extractNextProgrammeDetail(data, index, u'<p>', u'</p>')
		subdata, index = self.extractNextProgrammeDetail(data, index, u'<p>', u'/p>')
		actors = None
		director = None
		if subdata:
			actors, index = self.extractNextProgrammeDetail(subdata, 0, u'Medvirkende:</strong> ', u'<')
			director, index = self.extractNextProgrammeDetail(subdata, 0, u'Instruktør:</strong> ', u'<')
		
		return self.makeProgrammeInfoList(progid=progid, start=start, stop=stop, title=title, actors=actors, desc=desc, director=director, format=format, sound=sound, prevshown=prevshown, subtitles=subtitles)
	
	def retrieveProgrammeDetails (self, prog):
		programmeDetails = None
		url = u'http://yousee.tv/modal/tvguide_programinfo/'+prog[self.infoMap['id']]
		data = self.getWebPage(url, 3)
		if data:
			programmeDetails = self.extractProgrammeDetails (data, prog[self.infoMap['id']])
		if programmeDetails:
			#if not programmeDetails[self.infoMap['start']]:
			programmeDetails[self.infoMap['start']] = prog[self.infoMap['start']]
			#if not programmeDetails[self.infoMap['stop']]:
			programmeDetails[self.infoMap['stop']] = prog[self.infoMap['stop']]
			if not programmeDetails[self.infoMap['title']]:
				programmeDetails[self.infoMap['title']] = prog[self.infoMap['title']]
		else:
			programmeDetails = prog
			sys.stderr.write("Could not get programme details for %s\n" % prog[self.infoMap['id']])
		return programmeDetails
	
	def correctTimes(self, day, programme):
		if programme:
			# Convert all times to real date+time objects
			for index in range(len(programme)):
				# Localization is done later, since this can only
				# be done after we have moved programs to the correct day
				if programme[index][self.infoMap['start']]:
					programme[index][self.infoMap['start']] = self.makeTime(programme[index][self.infoMap['start']], day)
				else:
					sys.stderr.write("Error: No start time! Skipping programme\n")
					return []

				if programme[index][self.infoMap['stop']]:
					programme[index][self.infoMap['stop']] = self.makeTime(programme[index][self.infoMap['stop']], day)
				else:
					sys.stderr.write("Warning: No end time. - Will construct one from next start time.\n")
			# Check for midnight shift. It could look like either of the next three lines:
			# yesterday, today, today, today, tomorrow, tomorrow -end
			# today, today, tomorrow, tomorrow -end
			# tomorrow, tomorrow -end
			# depending on if we check slightly past midnight or not
			if not programme[0][self.infoMap['start']]: return []
			if programme[0][self.infoMap['stop']]:
				if programme[0][self.infoMap['start']] > programme[0][self.infoMap['stop']]:
					# We are just past midnight with current programme started the day before
					programme[0][self.infoMap['start']] -= datetime.timedelta(1)
			lastTime = programme[0][self.infoMap['start']]
			timeShift = False
			hasEnd = True
			for index in range(len(programme)):
				# Exit if we are missing a start time
				if not programme[index][self.infoMap['start']]: return []
				if timeShift:
					# We have already found a timeshift, just shift the time
					programme[index][self.infoMap['start']] += datetime.timedelta(1)
					# Add end time to last programme if missing
					if not hasEnd:
						programme[index-1][self.infoMap['stop']] = programme[index][self.infoMap['start']]
						hasEnd = True
					if programme[index][self.infoMap['stop']]:
						programme[index][self.infoMap['stop']] += datetime.timedelta(1)
					else:
						hasEnd = False
				else:
					# Test for time shifts
					if lastTime > programme[index][self.infoMap['start']]:
						# Timeshift from last prog to this
						timeShift = True
						programme[index][self.infoMap['start']] += datetime.timedelta(1)
						# Add end time to last programme if missing
						if not hasEnd:
							programme[index-1][self.infoMap['stop']] = programme[index][self.infoMap['start']]
							hasEnd = True
						if programme[index][self.infoMap['stop']]:
							programme[index][self.infoMap['stop']] += datetime.timedelta(1)
						else:
							hasEnd = False
					else:
						if not hasEnd:
							programme[index-1][self.infoMap['stop']] = programme[index][self.infoMap['start']]
							hasEnd = True
						if programme[index][self.infoMap['stop']]:
							if programme[index][self.infoMap['start']] > programme[index][self.infoMap['stop']]:
								# We have a timeshift from start to stop
								timeShift = True
								programme[index][self.infoMap['stop']] += datetime.timedelta(1)
							lastTime = programme[index][self.infoMap['stop']]
						else:
							hasEnd = False
							lastTime = programme[index][self.infoMap['start']]

			# Now, we are ready for localization
			for index in range(len(programme)):
				# Play it safe around shift from summer to winter time (daylight savings)
				# Hmm, but then the programme can overlap...
				# If a time do not exist, suppose it is because it is without daylight savings
				# so try to add an hour and localize that
				for tag in ['start','stop']:
					if programme[index][self.infoMap[tag]]:
						try:
							programme[index][self.infoMap[tag]] = self.dktz.localize(programme[index][self.infoMap[tag]], is_dst = True)
						except IndexError:
							programme[index][self.infoMap[tag]] = self.dktz.localize(programme[index][self.infoMap[tag]] + datetime.timedelta(hours=1), is_dst = True)

		return programme
	
	def removeOutOfTime(self, programme):
		if programme:
			index = 0
			while index < len(programme):
				if (programme[index][self.infoMap['start']] < self.startTime) or  (programme[index][self.infoMap['start']] >= self.stopTime):
					programme.pop(index)
				else:
					index += 1
	
	def retrieveDayProgramme (self, channel, channelUrl, day):
		programme = []
		if not self.quiet: sys.stderr.write("Retrieving programme for %s on day %s\n" % (channel,day+1))
		programme = self.retrieveBaseDayProgramme(channel, channelUrl, day)
		programme = self.correctTimes(day, programme)
		self.removeOutOfTime(programme)
		if programme:
			if self.retrieveDetails:
				for index in range(len(programme)):
					programmeDetails = self.retrieveProgrammeDetails(programme[index])
					if programmeDetails:
						programme[index] = programmeDetails
		else:
			sys.stderr.write("Nothing found for %s on day %s\n" % (channel,day+1))
		return programme
	
	def cleanDuplicates(self): # TODO?
		# infoMap: id, start, stop, title, origtitle, actors, desc, director, country, category, date
		for channel, channelUrl, channelActive, xmltvId in self.channels:
			if channelActive:
				idlist = []
				programme = self.programme[channel]
				index = 0
				while index < len(programme):
					progid = programme[index][self.infoMap['id']]
					if progid in idlist:
						programme.pop(index)
					else:
						idlist.append(progid)
						index += 1
	
	def retrieveAllProgramme (self, details=True, firstDay=0, lastDay=6):
		self.retrieveDetails = details
		self.programme = {}
		for channel, channelUrl, channelActive, xmltvId in self.channels:
			if channelActive: self.programme[channel] = []
		if firstDay <= self.maxDays:
			for day in range(firstDay, lastDay+1):
				for channel, channelUrl, channelActive, xmltvId in self.channels:
					if channelActive:
						programme = self.retrieveDayProgramme(channel, channelUrl, day)
						if programme:
							self.programme[channel] += programme
		self.cleanDuplicates()
	
	def getAllProgramme (self):
		return self.programme
	
	def writeXMLLine (self, file, string, indent=0):
		indentStr = u''
		for i in range(indent):
			indentStr += u'\t'
		print >> file, indentStr+string
	
	def writeXMLChannels (self, file, indent=0):
		for channel, channelUrl, channelActive, xmltvId in self.channels:
			if self.listchannels or (channelActive and self.programme[channel]):
				self.writeXMLLine(file, u'<channel id="'+xmltvId+u'">', indent)
				self.writeXMLLine(file, u'<display-name>'+channel+u'</display-name>', indent+1)
				self.writeXMLLine(file, u'</channel>', indent)
	
	def writeXMLProgramme (self, file, indent=0):
		# (title+ , sub-title* , desc* , credits? , date? , category* , language? , orig-language? , length? , icon* , url* , country* , episode-num* , video? , audio? , previously-shown? , premiere? , last-chance? , new? , subtitles* , rating* , star-rating?)
		# infoMap: id, start, stop, title, actors, desc, director, sub-title
		for channel, channelUrl, channelActive, xmltvId in self.channels:
			if channelActive:
				programme = self.programme[channel]
				for p in programme:
					self.writeXMLLine(file, u'<programme start="'+p[self.infoMap['start']].strftime(self.timeformat)+u'" stop="'+p[self.infoMap['stop']].strftime(self.timeformat)+u'" channel="'+xmltvId+u'">', indent)
					
					if p[self.infoMap['title']]:
						self.writeXMLLine(file, u'<title lang="da">'+p[self.infoMap['title']]+u'</title>', indent+1)
					else:
						self.writeXMLLine(file, u'<title lang="da">Ukendt titel</title>', indent+1)

					if p[self.infoMap['sub-title']]:
						self.writeXMLLine(file, u'<sub-title lang="da">'+p[self.infoMap['sub-title']]+u'</sub-title>', indent+1)

					if p[self.infoMap['desc']]:
						self.writeXMLLine(file, u'<desc lang="da">'+p[self.infoMap['desc']]+u'</desc>', indent+1)
					
					if p[self.infoMap['actors']] or p[self.infoMap['director']]:
						self.writeXMLLine(file, u'<credits>', indent+1)
						if p[self.infoMap['director']]:
							for director in p[self.infoMap['director']]:
								self.writeXMLLine(file, u'<director>'+director+u'</director>', indent+2)
						if p[self.infoMap['actors']]:
							for actor in p[self.infoMap['actors']]:
								self.writeXMLLine(file, u'<actor>'+actor+u'</actor>', indent+2)
						self.writeXMLLine(file, u'</credits>', indent+1)
					
					if p[self.infoMap['video-format']]:
						self.writeXMLLine(file, u'<video>', indent+1)
						self.writeXMLLine(file, u'<aspect>'+p[self.infoMap['video-format']]+u'</aspect>', indent+2)
						self.writeXMLLine(file, u'</video>', indent+1)
					
					if p[self.infoMap['stereo']]:
						self.writeXMLLine(file, u'<audio>', indent+1)
						self.writeXMLLine(file, u'<stereo>'+p[self.infoMap['stereo']]+u'</stereo>', indent+2)
						self.writeXMLLine(file, u'</audio>', indent+1)
					
					if p[self.infoMap['previously-shown']]:
						self.writeXMLLine(file, u'<previously-shown></previously-shown>', indent+1)
					
					if p[self.infoMap['subtitles']]:
						self.writeXMLLine(file, u'<subtitles type="'+p[self.infoMap['subtitles']]+'"></subtitles>', indent+1)
					
					self.writeXMLLine(file, u'</programme>', indent)
	
	def writeXML (self, file):
		self.writeXMLLine(file, u'<?xml version="1.0" encoding="'+self.outputEncoding+'"?>', 0)
		self.writeXMLLine(file, u'<!DOCTYPE tv SYSTEM "xmltv.dtd">', 0)
		
		self.writeXMLLine(file, u'<tv source-info-url="http://yousee.dk/tvguide"  generator-info-name="'+self.progname+u'/'+self.version+u'">',  0)
		
		self.writeXMLLine(file, u'', 0)
		self.writeXMLChannels (file, 1)
		if not self.listchannels:
			self.writeXMLLine(file, u'', 0)
			self.writeXMLProgramme (file, 1)
		self.writeXMLLine(file, u'</tv>', 0)

	def save(self, filename):
		try:
			output = codecs.open(filename, 'w', 'utf-8')
		except:
			return False
		succes = True
		try:
			output.write(u'#!/usr/bin/env python\n')
			output.write(u'# -*- coding: utf-8 -*-\n\n')
			output.write(u'import datetime\n')
			output.write(u'\n')
			output.write(u"progname  = u'"+self.progname      +u"'\n")
			output.write(u"version   = u'"+self.version       +u"'\n")
			output.write(u'channels  = '+str(self.channels)  +u'\n')
			output.write(u'programme = '+str(self.programme) +u'\n')
		except:
			sys.stderr.write("Could not save the programme!\n")
			succes = False
		output.close()
		return succes
	
	def load(self, filename):
		loadLocals = {}
		try:
			execfile(filename, globals(), loadLocals)
			if self.progname != loadLocals['progname']:
				return False
			if self.version != loadLocals['version']:
				return False
			self.channels = loadLocals['channels']
			self.programme = loadLocals['programme']
			return True
		except:
			return False
	
	def activateChannel(self, channel):
		# (channel, channelUrl, active, xmltv id)
		for index in range(len(self.channels)):
			if self.channels[index][0] == channel:
				channel, channelUrl, active, xmltvid = self.channels[index]
				self.channels[index] = (channel, channelUrl, True, xmltvid)

	def activateAllChannels(self):
		# (channel, channelUrl, active, xmltv id)
		for index in range(len(self.channels)):
			channel, channelUrl, active, xmltvid = self.channels[index]
			self.channels[index] = (channel, channelUrl, True, xmltvid)
	
	def deactivateChannel(self, channel):
		# (channel, channelUrl, active, xmltv id)
		for index in range(len(self.channels)):
			if self.channels[index][0] == channel:
				channel, channelUrl, active, xmltvid = self.channels[index]
				self.channels[index] = (channel, channelUrl, False, xmltvid)

	def deactivateAllChannels(self):
		# (channel, channelUrl, active, xmltv id)
		for index in range(len(self.channels)):
			channel, channelUrl, active, xmltvid = self.channels[index]
			self.channels[index] = (channel, channelUrl, False, xmltvid)

	def listChannels(self, file):
		self.writeXML(file)

	def interactiveConfigure(self):
		if not self.output:
			sys.stderr.write("A configuration is started, but you pipe the output to something.\n")
			sys.stderr.write("You properly want to ctrl-c out now and run it again without piping the output.\n")
		print ""
		for channel, channelUrl, channelActive, xmltvId in self.getChannels():
			answer = '-'
			while answer not in ['y', 'n', '']:
				if channelActive: answer = raw_input('Activate channel "%s" (Y/n) ' % channel)
				else: answer = raw_input('Activate channel "%s" (y/N) ' % channel)
				answer = answer.lower()
			if answer == 'y' or (channelActive and answer == ''):
				self.activateChannel(channel)
			else:
				self.deactivateChannel(channel)
		
		print "Saving channel configuration in", self.configFile
		self.saveChannels(self.configFile)
		print "You can change active channels and xmltv id's by hand in this file."
		print "But be carefull with the format as this code is not error tolerant."
	
	def run(self):
		if not self.quiet: sys.stderr.write("Starting the YouSee Grabber\n")
		
		status = self.checkSetup()
		if status < 0: return status
		
		file = sys.stdout
		fileOutput = False
		if self.output:
			try:
				file = codecs.open(self.output, 'w', self.outputEncoding, errors='xmlcharrefreplace')
				fileOutput = True
			except:
				sys.stderr.write('Could not open output file "'+self.output+'"\n')
				return self.errorCouldNotOpenOutput
		if self.forcedEncoding and not fileOutput:
			sys.stdout = codecs.getwriter(self.outputEncoding)(sys.stdout, errors='xmlcharrefreplace')
		
		firstDay = self.offset
		lastDay = self.offset + self.days - 1
		self.startTime = datetime.datetime.combine(self.startDay, datetime.time(0))
		self.startTime += datetime.timedelta(self.offset)
		self.stopTime = self.startTime + datetime.timedelta(self.days)
		self.startTime = self.dktz.localize(self.startTime,  is_dst=True)
		self.stopTime = self.dktz.localize(self.stopTime,  is_dst=True)
		# YouSee days starts at 06:00 if it is not the current day
		# so start the day before if not today
		if firstDay > 0:
			firstDay -= 1
		
		if not self.quiet: sys.stderr.write("Loading configuration\n")
		if not grabber.loadChannels(self.configFile):
			sys.stderr.write("Configuration file %s does not exist or is not usable.\n" % self.configFile)
			sys.stderr.write("Retrieving a channel list from Internet\n")
			self.configure = True
			grabber.retrieveChannels()
			
		if self.listchannels:
			self.listChannels(file)
		elif self.configure:
			self.interactiveConfigure()
		else:
			if not self.quiet:
				sys.stderr.write("Retrieving in interval "+str(self.startTime)+" to "+str(self.stopTime)+"\n")
			grabber.retrieveAllProgramme(self.retrieveDetails, firstDay, lastDay)
			grabber.writeXML(file)
			
			if sys.stdout.isatty() and not fileOutput:
				sys.stderr.write("Weird enough it looks like the output was written to the console.\n")
				sys.stderr.write("I have tried to guess the console character encoding to make it look correct.\n")
			
		return self.statusOk


if __name__ == "__main__":
	
	import os
	
	# Snatched from http://kofoto.rosdahl.net/trac/wiki/UnicodeInPython
	#sys.stdin  = codecs.getreader(get_file_encoding(sys.stdin))(sys.stdin)
	#sys.stdout = codecs.getwriter(get_file_encoding(sys.stdout))(sys.stdout)
	#sys.stderr = codecs.getwriter(get_file_encoding(sys.stderr))(sys.stderr)
	# End of snatch
	
	sys.stderr = codecs.getwriter(get_file_encoding(sys.stderr))(sys.stderr, errors='backslashreplace')
	if sys.stdout.isatty():
		sys.stdout = codecs.getwriter(get_file_encoding(sys.stdout))(sys.stdout, errors='backslashreplace')
	else:
		sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
	
	grabber = YouSeeGrabber()
	status = grabber.parseArguments(sys.argv)
	if status == grabber.statusOk: status = grabber.run()
	
	sys.exit(status)
