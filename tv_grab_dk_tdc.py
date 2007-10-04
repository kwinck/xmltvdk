#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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
# - make it follow the recomendations from xmltv: http://xmltv.org/wiki/xmltvcapabilities.html
#     Capability "manualconfig" refers to a perl library - is this necessary?
#     GUI config missing
# - Handling of screwed up guide data from tdc
# - Usage information (pytz, ...)
# - Do not add times for missing end times - leave it to user app.
# - Check time arithmetic according to http://pytz.sourceforge.net/ (normalize)
# - Split and merge channel programmes as used by tdc cable net
# - More complete handling of unexpected webpage layout
# - More complete error handling
# - Code comments

# Changelog
#
# 2007-03-21: This changelog is stopped, since it is now under subversion control.
#
# 2007-01-02: Version 0.98
# 	- Output is set to utf-8 unless it is to concole or forced by option
# 	- Find the users home with os.path.expanduser() - Should be more portable
#
# 2006-12-28: Version 0.97
# 	- Only write channels in output if they have any programme data.
# 	- Corrected timezone handling.
# 	  Still missing good solution for change from summer daylight savings to winter
# 	- Changed command line parameter parsing and program start
# 	- Default xmltv id's is cleaned for bad chars
# 	- Only give data on the days specified
# 	- Added capabilities baseline and manualconfig
# . - Passing tv_validate_grabber :-)
# 
# 2006-12-27: Version 0.96
# 	- Fixed problem with ',' after last person, when splitting person lists
# 	- Fix in person splitted (Roger was splittet to R and er)
# 
# 2006-12-27: Version 0.95
# 	- Fixed bug with reading stdin
# 
# 2006-12-27: Version 0.94
# 	- Fixed bug for users without pytz module
# 
# 2006-12-26: Version 0.93
# 	- changed output tag order to follow xmltv dtd
# 	- Added --capabilities option (xmltv recomendation)
# 	- Added exit on keyboard interrupt
# 	- By default output xmltv programme to stdout
# 	- Use stderr as output for most things to not interrupt with xmltv
# 	  programme to stdout
# 	- Changed --first-day and --last-day to --days and --offset
# 	- Added more encoding stuff to make it work with stdout and piping.
# 	  Now output encoding depends on locale used when using stdout.
# 	- Changed standard config file name
# 	- Added possibility to interrupt by ctrl-c
# 	- Timezone data added. Needs pytz module.
# 	  Ignoring timezones if pytz can not load.
# 	- Output passes tv_validate_file test from xmltv package :-)
# 	  But only if you use proper xmltv channel id's:
# 	  All xmltvids must match the regexp /^[-a-zA-Z0-9]+(\.[-a-zA-Z0-9]+)+$/.
# 
# 2006-12-26: Version 0.92
# 	- Added spliting of title to main title and subtitle
# 	- Added actors and directors
# 	- Added base class for grabbers
# 	- Corrected stripping of whitespace for some parts
# 	- Category is working again
# 	- Production date is working
# 	- Warning on format change for some parts
# 	- Added todo list
# 	- Added quiet mode (option --quiet)
# 
# 2006-12-26: Version 0.91
# 	- Removal of tabs and newlines around description in xmltv output.
# 	- Added unicode throughout code. Solved xmltv id Kanl_København for me.
# 	- Added --first-day and --last-day options.
# 	- Added credits, license and Changelog
# 
# 2006-12-25: Version 0.9
# 	Initial version.


import cookielib
import urllib2
import datetime
import codecs
import locale
import sys
try:
	import pytz
except:
	class PyTZ:
		def timezone(self, tzstring):
			return None
	pytz = PyTZ()
	class FakeTimezone:
		def localize(self, dt, is_dst=None):
			return dt

# Snatched from http://kofoto.rosdahl.net/trac/wiki/UnicodeInPython
def get_file_encoding(f):
	if hasattr(f, "encoding") and f.encoding:
		return f.encoding
	else:
		return locale.getpreferredencoding()
# End of snatch

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
		self.gui = False
		self.offset = 0
		self.days = None
		self.output = None
		
		self.outputEncoding = 'UTF-8'
		# Danish timezone
		self.dktz = pytz.timezone('Europe/Copenhagen')
		if self.dktz:
			self.timeformat = '%Y%m%d%H%M %z'
		else:
			self.timeformat = '%Y%m%d%H%M'
			self.dktz = FakeTimezone()
	
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
		#sys.stderr.write("     Indicate a wich for graphical information/questions (not supported yet)\n")
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


class TDCGrabber(BaseTVGrabber):
	
	def __init__(self, initSession=False, developerInfo=False):
		BaseTVGrabber.__init__(self)
		
		self.progname = u'tv_grab_dk_tdc'
		self.version = u'0.99'
		self.description = u'Denmark (tvguide.tdconline.dk)'
		self.capabilities = ['baseline', 'manualconfig']
		self.defaultConfigFile = self.xmltvDir + '/tv_grab_dk_tdc.conf'
		self.configFile = self.defaultConfigFile
		
		self.offset = 0
		self.maxDays = 7
		self.days = self.maxDays
		
		self.developerInfo = developerInfo
		self.weekDay = {u'mand':1,u'tirs':2,u'onsd':3,u'tors':4,u'fred':5,u'lørd':6,u'sønd':7}
		self.startDay = datetime.date.today()
		self.yesterday = self.startDay - datetime.timedelta(1)
		self.relativeDay = -100
		self.pageLoadTries = 3
		self.channels = []
		self.programme = {}
		self.retrieveDetails = True
		self.infoMap = {'id':0,'start':1,'stop':2,'title':3,'origtitle':4,'actors':5,'desc':6,'director':7,'country':8,'category':9,'date':10,'sub-title':11,'orig-sub-title':12}
		self.webPageEncoding = 'iso-8859-1'
		self.opener = None
		self.forcedEncoding = False
		
		if initSession:
			self.newSession()
	
	def printUsage(self):
		BaseTVGrabber.printUsage(self)
		sys.stderr.write(" --no-details\n")
		sys.stderr.write("     Drop details thereby making it a lot faster\n")
		sys.stderr.write(" --output-encoding\n")
		sys.stderr.write("     Output encoding to use (defaults to UTF-8)\n")
		
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
		url = 'http://portal.yousee.dk/ktvTVGuide/tvguide.portal'
		data = self.getWebPage(url, 10)
		self.setViewMode()
		self.relativeDay = -100
		if day != None:
			self.setDay(day)
	
	def setViewMode (self):
		url = 'http://portal.yousee.dk:80/ktvTVGuide/tvguide.portal?_nfpb=true&tvguideimageNavigation_portlet_1_actionOverride=%2Fportlets%2Ftvguide%2FimageNavigation%2FselectViewAction&tvguideimageNavigation_portlet_1%7BactionForm.currentPresentationType%7D=horz'
		data = self.getWebPage(url, 10)
		return data != None

	def setDay (self, day):
		if day != self.relativeDay:
			self.relativeDay = day
			url = 'http://portal.yousee.dk:80/ktvTVGuide/tvguide.portal?_nfpb=true&tvguideimageNavigation_portlet_1_actionOverride=%2Fportlets%2Ftvguide%2FimageNavigation%2FselectTimeAction&tvguideimageNavigation_portlet_1wlw-select_key:%7BactionForm.chosenTimeSpanOption%7D=' + str(day)
			data = self.getWebPage(url, 10)
			if not data:
				return False
		return True

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

	def extractChannelPackages (self, data):
		packages = []
		index = 0
		while index >= 0:
			index = data.find(u'tvguide-leftmenu-listentry', index)
			if index >= 0:
				packageIdx = self.extractElement(data, index, u'tvguidemenu_portlet_1{actionForm.channelPackageIdx}')
				if packageIdx and (packageIdx not in packages):
					packages.append(packageIdx)
				index += 1
		return packages

	def extractChannels (self, data):
		index = 0
		while index >= 0:
			index = data.find(u'tvguide-leftmenu-low-listentry', index)
			if index >= 0:
				channel = self.extractElement(data, index, u'tvguidemenu_portlet_1{actionForm.channel}')
				if channel:
					channelPackageIdx = self.extractElement(data, index, u'tvguidemenu_portlet_1{actionForm.channelPackageIdx}')
					channelIdx = self.extractElement(data, index, u'tvguidemenu_portlet_1{actionForm.channelIdx}')
					xmltvId = self.cleanChannelId(channel+u'.tdckabeltv.dk')
					while xmltvId in [xi for c,cpi,ci,a,xi in self.channels]:
						xmltvId += '-X'
					self.channels.append( (channel, channelPackageIdx, channelIdx, False, xmltvId) )
				index += 1
	
	def retrieveChannels (self):
		self.channels = []
		channelPackages = []
		
		if not self.quiet: sys.stderr.write("Retrieving channel packages\n")
		url = 'http://portal.yousee.dk/ktvTVGuide/tvguide.portal'
		data = self.getWebPage(url, 10)
		if data:
			channelPackages = self.extractChannelPackages(data)
			if not self.quiet: sys.stderr.write("Found following packages: %s\n" % channelPackages)
		else:
			sys.stderr.write("Could not load page\n")
		
		for channelgroup in channelPackages:
			url = 'http://portal.yousee.dk:80/ktvTVGuide/tvguide.portal?_nfpb=true&tvguidemenu_portlet_1_actionOverride=%2Fportlets%2Ftvguide%2Fmenu%2FselectChannelGroupAction&tvguidemenu_portlet_1%7BactionForm.channelPackageIdx%7D=' + channelgroup
			data = self.getWebPage(url, 10)
			if data:
				if not self.quiet: sys.stderr.write("Retrieving channels for package %s\n" % channelgroup)
				self.extractChannels (data)
			else:
				sys.stderr.write("Could not get channels for package %s\n" % channelgroup)
	
	def getChannels (self):
		return self.channels
	
	def loadChannels (self, filename):
		loadLocals = {}
		try:
			execfile(filename, globals(), loadLocals)
			self.channels = loadLocals['channels']
			if (not loadLocals.has_key('version')) or (loadLocals['version'] == u'0.9'):
				sys.stderr.write("Warning: You should update %s by deleting the old and make a new\n" % filename)
				sys.stderr.write("Sorry for the inconvienence\n")
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
			output.write(u'# -*- coding: UTF-8 -*-\n')
			output.write(u'\n')
			output.write(u"progname  = u'"+self.progname  +u"'\n")
			output.write(u"version   = u'"+self.version   +u"'\n")
			output.write(u'\n')
			output.write(u'# If you edit this file by hand, only change active and xmltvid columns.\n')
			output.write(u'# (channel, channelPackageIdx, channelIdx, active, xmltvid)\n')
			output.write(u'channels = [\n')
			for ch in self.channels[:-1]:
				output.write(str(ch) + u',\n')
			output.write(str(self.channels[-1]) + u']\n')
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
	
	def makeProgrammeInfoList(self, progid, start=None, stop=None, title=None, origtitle=None, actors=None, desc=None, director=None, country=None, category=None, date=None):
		info = [None]*len(self.infoMap)
		info[self.infoMap['id']] = progid
		info[self.infoMap['start']] = start
		info[self.infoMap['stop']] = stop
		info[self.infoMap['title']], info[self.infoMap['sub-title']] = self.splitTitle(title)
		info[self.infoMap['origtitle']], info[self.infoMap['orig-sub-title']] = self.splitTitle(origtitle)
		info[self.infoMap['actors']] = self.splitPersons(actors)
		info[self.infoMap['desc']] = desc
		info[self.infoMap['director']] = self.splitPersons(director)
		info[self.infoMap['country']] = country
		info[self.infoMap['category']] = category
		info[self.infoMap['date']] = date
		return info
	
	def extractBaseProgramme(self, data):
		programme = []
		# Run through every programme section
		index = 0
		while index >= 0:
			# This string indicates a programme section start
			index = data.find(u'tvguideresultPresentation_portlet_1', index)
			if index != -1:
				index2 = data.find(u'</form>', index)
				# Get the programme id
				programmeId = self.extractElement(data, index, u'tvguideresultPresentation_portlet_1{actionForm.udsendelsesId}')
				if programmeId:
					start, index = self.extractNextProgrammeDetail(data, index, u'<span>', u'</span>')
					if index >= index2: start = None
					stop,  index = self.extractNextProgrammeDetail(data, index, u'<span>', u'</span>')
					if index >= index2: stop = None
					title, index = self.extractNextProgrammeDetail(data, index, u'<span>', u'</span>')
					if index >= index2: title = None
					programme.append(self.makeProgrammeInfoList(progid=programmeId, start=start, stop=stop, title=title))
				index = index2
		return programme
	
	def retrieveBaseDayProgramme(self, channel, channelPackageIdx, channelIdx, day):
		baseProgramme = []
		# Set the day we want a programme for
		self.setDay(day)
		# fetch the page with the base programme (no details
		url = 'http://portal.yousee.dk:80/ktvTVGuide/tvguide.portal?_nfpb=true&tvguidemenu_portlet_1_actionOverride=%2Fportlets%2Ftvguide%2Fmenu%2FselectChannelAction&tvguidemenu_portlet_1%7BactionForm.channel%7D='+self.cleanForURL(channel)+'&tvguidemenu_portlet_1%7BactionForm.channelPackageIdx%7D='+channelPackageIdx+'&tvguidemenu_portlet_1%7BactionForm.channelIdx%7D='+channelIdx
		data = self.getWebPage(url, 10)
		if data:
			# Check the week day and thereby set the date
			daySeven = self.extractDaySeven (data)
			if not daySeven:
				sys.stderr.write("Could not find the day!\n")
				return None
			if daySeven != self.yesterday.isoweekday():
				# The day has changed
				self.yesterday += datetime.timedelta(1)
				if daySeven != self.yesterday.isoweekday():
					# Something is wrong the day has changed, but not to the next!
					sys.stderr.write("Error with days!\n")
					return None
			# Parse the base programme
			baseProgramme = self.extractBaseProgramme(data)
		else:
			sys.stderr.write("Could not get programme for %s\n" % channel)
		return baseProgramme
	
	def stripHTMLSpecials (self, data):
		# replace '& ' with '&amp; '
		data = data.replace(u'& ', u'&amp; ')
		# remove all '<br />'
		data = data.replace(u'<br />', u' ')
		# remove all '&nbsp;'
		data = data.replace(u'&nbsp;', u' ')
		
		return data
	
	def parseWooblyInfoSkipEmptyLines (self, data, index):
		linecount = 0
		index1 = index
		index2 = data.find(u'\n', index1) + len(u'\n')
		while index2 >= 0 + len(u'\n') and len(data[index1:index2].strip()) == 0:
			linecount += 1
			index1 = index2
			index2 = data.find(u'\n', index1) + len(u'\n')
		if index2 == len(u'\n') - 1: index1 = -1
		return index1, linecount
	
	def parseWooblyInfo (self, data):
		country, category, date = None, None, None
		if not data: return country, category, date
		index, lines = self.parseWooblyInfoSkipEmptyLines(data, 0)
		if index == -1: return country, category, date
		if lines == 1:
			index2 = data.find(u'\n', index)
			if index2 >= 0:
				country = self.stripHTMLSpecials(data[index:index2]).strip()
				index, lines = self.parseWooblyInfoSkipEmptyLines(data, index2 + 1)
				if index == -1: return country, category, date
		if lines == 3:
			index2 = data.find(u'\n', index)
			if index2 >= 0:
				category = self.stripHTMLSpecials(data[index:index2]).strip()
				index, lines = self.parseWooblyInfoSkipEmptyLines(data, index2 + 1)
				if index == -1: return country, category, date
		if lines == 3:
			index = data.find(u'fra ', index)
			if index >= 0:
				index += len(u'fra ')
				index2 = data.find(u'\n', index)
				if index2 >= 0:
					date = self.stripHTMLSpecials(data[index:index2]).strip()
		else:
			if not self.wooblyWarning:
				sys.stderr.write("Warning: information format seems wrong. Data:\n")
				sys.stderr.write("%s\n" % data)
				self.wooblyWarning = 1
			else:
				self.wooblyWarning += 1
				sys.stderr.write("Warning %i: information format seems wrong.\n" % self.wooblyWarning)
		return (country, category, date)
	
	def makeTime (self, timeStr, relativeDay):
		# You always have two digits for minutes, so find it from behind
		try:
			hour = int(timeStr[0:-3])
			minute = int(timeStr[-2:])
		except:
			sys.stderr.write("Could not convert %s\n" % timeStr)
			return None
		date = self.yesterday + datetime.timedelta(relativeDay)
		try:
			time = datetime.time(hour, minute)
		except:
			sys.stderr.write("Could not convert %s\n" % timeStr)
			return None
		return datetime.datetime.combine(date, time)
	
	def extractProgrammeDetails (self, data, progid):
		index = data.find(u'detail-bar-info')
		index = data.find(u'>', index) + 1
		index2 = data.find(u'</div>', index)
		subdata = data[index:index2]
		index = 0
		start, index = self.extractNextProgrammeDetail(subdata, index, u'<span>', u'</span>')
		stop,  index = self.extractNextProgrammeDetail(subdata, index, u'<span>', u'</span>')
		title, index = self.extractNextProgrammeDetail(subdata, index, u'<span>', u'</span>')
		origtitle, index = self.extractNextProgrammeDetail(subdata, index, u'<b>(', u')</b>')
		infoarea, index  = self.extractNextProgrammeDetail(subdata, index, u'<b>\r\n', u'</b>\r\n', False)
		desc,   index = self.extractNextProgrammeDetail(subdata, index, u'<span>', u'</span>')
		actors, index = self.extractNextProgrammeDetail(subdata, index, u'                                    Med ', u'\n')
		director, index = self.extractNextProgrammeDetail(subdata, index, u'                                    Instrueret af ', u'\n')
		
		country, category, date = self.parseWooblyInfo(infoarea)
		
		return self.makeProgrammeInfoList(progid=progid, start=start, stop=stop, title=title, origtitle=origtitle, actors=actors, desc=desc, director=director, country=country, category=category, date=date)
	
	def retrieveProgrammeDetails (self, prog):
		programmeDetails = None
		url = 'http://portal.yousee.dk:80/ktvTVGuide/tvguide.portal?_nfpb=true&tvguideresultPresentation_portlet_1_actionOverride=%2Fportlets%2Ftvguide%2FresultPresentation%2FselectShowDetails&tvguideresultPresentation_portlet_1%7BactionForm.udsendelsesId%7D='+prog[self.infoMap['id']]
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
				# Play it safe around shift from summer to winter time (daylight savings)
				# Hmm, but then the programme can overlap...
				# If a time do not exist, suppose it is because it is without daylight savings
				# so try to add an hour and localize that
				if programme[index][self.infoMap['start']]:
					try:
						programme[index][self.infoMap['start']] = self.dktz.localize( self.makeTime(programme[index][self.infoMap['start']], day),  is_dst=True)
					except IndexError:
						programme[index][self.infoMap['start']] = self.dktz.localize( self.makeTime(programme[index][self.infoMap['start']], day) + datetime.timedelta(hours=1),  is_dst=True)
				if programme[index][self.infoMap['stop']]:
					try:
						programme[index][self.infoMap['stop']] = self.dktz.localize( self.makeTime(programme[index][self.infoMap['stop']], day), is_dst=False)
					except IndexError:
						programme[index][self.infoMap['stop']] = self.dktz.localize( self.makeTime(programme[index][self.infoMap['stop']], day) + datetime.timedelta(hours=1), is_dst=False)
				
				if not programme[index][self.infoMap['start']]:
					sys.stderr.write("Error: No start time! Skipping programme\n")
					return []
				if not programme[index][self.infoMap['stop']]:
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
		return programme
	
	def removeOutOfTime(self, programme):
		if programme:
			index = 0
			while index < len(programme):
				if (programme[index][self.infoMap['start']] < self.startTime) or  (programme[index][self.infoMap['start']] >= self.stopTime):
					programme.pop(index)
				else:
					index += 1
	
	def retrieveDayProgramme (self, channel, channelPackageIdx, channelIdx, day):
		programme = []
		if not self.quiet: sys.stderr.write("Retrieving programme for %s on day %s\n" % (channel,day))
		programme = self.retrieveBaseDayProgramme(channel, channelPackageIdx, channelIdx, day)
		programme = self.correctTimes(day, programme)
		self.removeOutOfTime(programme)
		if programme:
			if self.retrieveDetails:
				for index in range(len(programme)):
					programmeDetails = self.retrieveProgrammeDetails(programme[index])
					if programmeDetails:
						programme[index] = programmeDetails
		else:
			sys.stderr.write("Nothing found for %s on day %s\n" % (channel,day))
		return programme
	
	def cleanDuplicates(self):
		# infoMap: id, start, stop, title, origtitle, actors, desc, director, country, category, date
		for channel, channelPackageIdx, channelIdx, channelActive, xmltvId in self.channels:
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
	
	def retrieveAllProgramme (self, details=True, firstDay=1, lastDay=7):
		self.retrieveDetails = details
		self.programme = {}
		for channel, channelPackageIdx, channelIdx, channelActive, xmltvId in self.channels:
			if channelActive: self.programme[channel] = []
		if firstDay <= self.maxDays:
			for day in range(firstDay, lastDay+1):
				self.setDay(day)
				for channel, channelPackageIdx, channelIdx, channelActive, xmltvId in self.channels:
					if channelActive:
						programme = self.retrieveDayProgramme(channel, channelPackageIdx, channelIdx, day)
						if programme == []:
							self.newSession(day)
							programme = self.retrieveDayProgramme(channel, channelPackageIdx, channelIdx, day)
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
		for channel, channelPackageIdx, channelIdx, channelActive, xmltvId in self.channels:
			if channelActive and self.programme[channel]:
				self.writeXMLLine(file, u'<channel id="'+xmltvId+u'">', indent)
				self.writeXMLLine(file, u'<display-name>'+channel+u'</display-name>', indent+1)
				self.writeXMLLine(file, u'</channel>', indent)
	
	def writeXMLProgramme (self, file, indent=0):
		# (title+ , sub-title* , desc* , credits? , date? , category* , language? , orig-language? , length? , icon* , url* , country* , episode-num* , video? , audio? , previously-shown? , premiere? , last-chance? , new? , subtitles* , rating* , star-rating?)
		# infoMap: id, start, stop, title, origtitle, actors, desc, director, country, category, date
		for channel, channelPackageIdx, channelIdx, channelActive, xmltvId in self.channels:
			if channelActive:
				programme = self.programme[channel]
				for p in programme:
					self.writeXMLLine(file, u'<programme start="'+p[self.infoMap['start']].strftime(self.timeformat)+u'" stop="'+p[self.infoMap['stop']].strftime(self.timeformat)+u'" channel="'+xmltvId+u'">', indent)
					
					if p[self.infoMap['origtitle']]:
						self.writeXMLLine(file, u'<title>'+p[self.infoMap['origtitle']]+u'</title>', indent+1)
					if p[self.infoMap['title']]:
						self.writeXMLLine(file, u'<title lang="da">'+p[self.infoMap['title']]+u'</title>', indent+1)
					elif not p[self.infoMap['origtitle']]:
						self.writeXMLLine(file, u'<title lang="da">Unknown title</title>', indent+1)
					
					if p[self.infoMap['orig-sub-title']]:
						self.writeXMLLine(file, u'<sub-title>'+p[self.infoMap['orig-sub-title']]+u'</sub-title>', indent+1)
					if p[self.infoMap['sub-title']]:
						self.writeXMLLine(file, u'<sub-title lang="da">'+p[self.infoMap['sub-title']]+u'</sub-title>', indent+1)
					
					if p[self.infoMap['desc']]:
						self.writeXMLLine(file, u'<desc lang="da">'+p[self.infoMap['desc']]+u'</desc>', indent+1)
					
					if p[self.infoMap['actors']] or p[self.infoMap['director']]:
						self.writeXMLLine(file, '<credits>', indent+1)	
						if p[self.infoMap['director']]:
							for director in p[self.infoMap['director']]:
								self.writeXMLLine(file, '<director>'+director+'</director>', indent+2)
						if p[self.infoMap['actors']]:
							for actor in p[self.infoMap['actors']]:
								self.writeXMLLine(file, '<actor>'+actor+'</actor>', indent+2)
						self.writeXMLLine(file, '</credits>', indent+1)
					
					if p[self.infoMap['date']]:
						if len(p[self.infoMap['date']]) == 4 or len(p[self.infoMap['date']]) == 2:
							try:
								year = int(p[self.infoMap['date']])
								self.writeXMLLine(file, u'<date>'+p[self.infoMap['date']]+u'</date>', indent+1)
							except: pass
					
					if p[self.infoMap['category']]:
						self.writeXMLLine(file, u'<category lang="da">'+p[self.infoMap['category']]+u'</category>', indent+1)
					
					if p[self.infoMap['country']]:
						self.writeXMLLine(file, u'<country lang="da">'+p[self.infoMap['country']]+u'</country>', indent+1)
					
					self.writeXMLLine(file, u'</programme>', indent)
	
	def writeXML (self, file):
		self.writeXMLLine(file, u'<?xml version="1.0" encoding="'+self.outputEncoding+'"?>', 0)
		self.writeXMLLine(file, u'<!DOCTYPE tv SYSTEM "xmltv.dtd">', 0)
		
		self.writeXMLLine(file, u'<tv source-info-url="http://yousee.dk/privat/"  generator-info-name="'+self.progname+u'/'+self.version+u'">',  0)
		
		self.writeXMLLine(file, u'', 0)
		self.writeXMLChannels (file, 1)
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
			output.write(u'# -*- coding: UTF-8 -*-\n\n')
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
		# (channel, channelPackageIdx, channelIdx, active, xmltv id)
		for index in range(len(self.channels)):
			if self.channels[index][0] == channel:
				channel, channelPackageIdx, channelIdx, active, xmltvid = self.channels[index]
				self.channels[index] = (channel, channelPackageIdx, channelIdx, True, xmltvid)

	def activateAllChannels(self):
		# (channel, channelPackageIdx, channelIdx, active, xmltv id)
		for index in range(len(self.channels)):
			channel, channelPackageIdx, channelIdx, active, xmltvid = self.channels[index]
			self.channels[index] = (channel, channelPackageIdx, channelIdx, True, xmltvid)
	
	def deactivateChannel(self, channel):
		# (channel, channelPackageIdx, channelIdx, active, xmltv id)
		for index in range(len(self.channels)):
			if self.channels[index][0] == channel:
				channel, channelPackageIdx, channelIdx, active, xmltvid = self.channels[index]
				self.channels[index] = (channel, channelPackageIdx, channelIdx, False, xmltvid)

	def deactivateAllChannels(self):
		# (channel, channelPackageIdx, channelIdx, active, xmltv id)
		for index in range(len(self.channels)):
			channel, channelPackageIdx, channelIdx, active, xmltvid = self.channels[index]
			self.channels[index] = (channel, channelPackageIdx, channelIdx, False, xmltvid)
	
	def interactiveConfigure(self):
		print ""
		for channel, channelPackageIdx, channelIdx, channelActive, xmltvId in self.getChannels():
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
		if not self.quiet: sys.stderr.write("Starting TDCGrabber\n")
		
		status = self.checkSetup()
		if status < 0: return status
		
		file = sys.stdout
		fileOutput = False
		if self.output:
			try:
				file = codecs.open(self.output, 'w', self.outputEncoding)
				fileOutput = True
			except:
				sys.stderr.write('Could not open output file "'+self.output+'"\n')
				return self.errorCouldNotOpenOutput
		if self.forcedEncoding and not fileOutput:
			sys.stdout = codecs.getwriter(self.outputEncoding)(sys.stdout)
		
		firstDay = 1 + self.offset
		lastDay = self.offset + self.days
		self.startTime = datetime.datetime.combine(self.startDay, datetime.time(0))
		self.startTime += datetime.timedelta(self.offset)
		self.stopTime = self.startTime + datetime.timedelta(self.days)
		self.startTime = self.dktz.localize(self.startTime,  is_dst=True)
		self.stopTime = self.dktz.localize(self.stopTime,  is_dst=True)
		# TDC days starts at 06:00 if it is not the current day
		# so start the day before if not today
		if firstDay > 1:
			firstDay -= 1
		
		if not self.quiet: sys.stderr.write("Loading configuration\n")
		if not grabber.loadChannels(self.configFile):
			sys.stderr.write("Configuration file %s does not exist.\n" % self.configFile)
			sys.stderr.write("Retrieving a channel list from Internet\n")
			self.configure = True
			grabber.retrieveChannels()
			
		if self.configure:
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
	
	sys.stderr = codecs.getwriter(get_file_encoding(sys.stderr))(sys.stderr)
	if sys.stdout.isatty():
		sys.stdout = codecs.getwriter(get_file_encoding(sys.stdout))(sys.stdout)
	else:
		sys.stdout = codecs.getwriter('UTF-8')(sys.stdout)
	
	grabber = TDCGrabber()
	status = grabber.parseArguments(sys.argv)
	if status == grabber.statusOk: status = grabber.run()
	
	sys.exit(status)
