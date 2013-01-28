# by betonme @2012
#
#########################################
#
# !! Never make this file public !!
#
#########################################

# Imports
from Components.config import config

from Tools.BoundFunction import boundFunction

from urllib import urlencode

from iso8601 import parse_date
from HTMLParser import HTMLParser

from datetime import datetime

import re
from sys import maxint

# Internal
from Plugins.Extensions.SeriesPlugin.IdentifierBase import IdentifierBase
from Plugins.Extensions.SeriesPlugin.Channels import compareChannels
from Plugins.Extensions.SeriesPlugin.Logger import splog


# Constants
SERIESLISTURL     = "http://www.wunschliste.de/ajax/search_dropdown.pl?"
EPISODEIDURLATOM  = "http://www.wunschliste.de/xml/atom.pl?"
#EPISODEIDURLRSS  = "http://www.wunschliste.de/xml/rss.pl?"
EPISODEIDURLPRINT = "http://www.wunschliste.de/epg_print.pl?"

# Series: EpisodeTitle (Season.Episode) - Weekday Date, Time / Channel (Country)
# Two and a Half Men: Der Mittwochs-Mann (1.5) - Mi 02.05., 19.50:00 Uhr / TNT Serie (Pay-TV)
# Two and a Half Men: Der Mittwochs-Mann (1.5) - Mi 02.05., 19.50:00 Uhr / TNT Serie
# Two and a Half Men: Der Mittwochs-Mann (1) (1.5) - Mi 02.05., 19.50:00 Uhr / TNT Serie
# Der Troedeltrupp - Das Geld liegt im Keller: Folge 109 (109) - Do 03.05., 16.15:00 Uhr / RTL II
# Galileo: U.a.: Die schaerfste Chili der Welt - Fr 04.05., 19.05:00 Uhr / ProSieben
# Galileo: Magazin mit Aiman Abdallah, BRD 2012 - Mi 09.05., 06.10:00 Uhr / ProSieben
# Gute Zeiten, schlechte Zeiten: Folgen 4985 - 4988 (21.84) - Sa 05.05., 11.00:00 Uhr / RTL
# Channel is between last / and ( or line end
CompiledRegexpAtomChannel = re.compile('\/(?!.*\/) ([^\(]+)')
# Date is between last - and channel
CompiledRegexpAtomDate = re.compile('-(?!.*-) (.+)')
# Find optional episode
CompiledRegexpAtomEpisode = re.compile('\((?!.*\()(.+)\) ')
# Series: Title
CompiledRegexpAtomTitle = re.compile('.+: (.+)')

# (Season.Episode) - EpisodeTitle
# (21.84) Folge 4985
# (105) Folge 105
# (4.11/4.11) Mama ist die Beste/Rund um die Uhr
# Galileo: Die schaerfste Chili der Welt
# Galileo: Jumbo auf Achse: Muelltonnenkoch
# Gute Zeiten, schlechte Zeiten: Folgen 4985 - 4988 (21.84) - Sa 05.05., 11.00:00 Uhr / RTL
#CompiledRegexpPrintTitle = re.compile( '(\(.*\) )?(.+)')

CompiledRegexpEpisode = re.compile( '((\d+)[\.x])?(\d+)')


class WLAtomParser(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.title = False
		self.updated = False
		self.titlestr = ''
		self.updatedstr = ''
		self.list = []

	def handle_starttag(self, tag, attributes):
		if tag == 'title':
			self.title = True
		elif tag == 'updated':
			self.updated = True

	def handle_endtag(self, tag):
		if tag == 'title':
			self.title = False
		elif tag == 'updated':
			self.updated = False
		elif tag == 'entry':
			self.list.append( (self.titlestr, self.updatedstr) )
			self.titlestr = ''
			self.updatedstr = ''

	def handle_data(self, data):
		if self.title:
			self.titlestr += data
		elif self.updated:
			self.updatedstr = data


class WLPrintParser(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.tr= False
		self.td= False
		self.data = []
		self.list = []

	def handle_starttag(self, tag, attributes):
		if tag == 'td':
			self.td= True
		elif tag == 'tr':
			self.tr= True

	def handle_endtag(self, tag):
		if tag == 'td':
			self.td= False
		elif tag == 'tr':
			self.tr= False
			self.list.append(self.data)
			self.data= []

	def handle_data(self, data):
		if self.tr and self.td:
			self.data.append(data)


class Wunschliste(IdentifierBase):
	def __init__(self):
		IdentifierBase.__init__(self)

	@classmethod
	def knowsToday(cls):
		# Use the print page
		return True

	@classmethod
	def knowsFuture(cls):
		# Use the atom feed
		return True

	def getEpisode(self, name, begin, end=None, service=None, channels=[]):
		# On Success: Return a single season, episode, title tuple
		# On Failure: Return a empty list or None
		
		self.license = None
		
		self.name = name
		self.begin = begin
		self.end = end
		self.service = service
		self.channels = channels
		self.ids = []
		self.when = 0
		
		self.returnvalue = None
		
		# Check preconditions
		if not name:
			splog(_("Skip Wunschliste: No show name specified"))
			return _("Skip Wunschliste: No show name specified")
		if not begin:
			splog(_("Skip Wunschliste: No begin timestamp specified"))
			return _("Skip Wunschliste: No begin timestamp specified")
		
		splog("Wunschliste getEpisode")
		
		#Py2.6
		delta = abs(datetime.now() - self.begin)
		delta = delta.seconds + delta.days * 24 * 3600
		#Py2.7 delta = abs(datetime.now() - self.begin).total_seconds()
		if delta > 3*60*60:
			self.when = True
		else:
			self.when = False
		
		return self.getSeries()

	def getAlternativeSeries(self):
		self.name = " ".join(self.name.split(" ")[:-1])
		if self.name:
			return self.getSeries()
		else:
			return ( self.returnvalue or _("No matching series found") )
	
	def getSeries(self):
		url = SERIESLISTURL + urlencode({ 'q' : self.name })
		data = self.getPageInternal( url )
		
		serieslist = []
		
		if data and isinstance(data, basestring):
			for line in data.splitlines():
				values = line.split("|")
				if len(values) == 3:
					idname, countryyear, id = values
					splog(id, idname)
					serieslist.append( (id, idname) )
				else:
					splog("Wunschliste: ParseError: " + str(line))
			serieslist.reverse()
			
			data = serieslist
			self.doCache(url, data)
		
		if data and isinstance(data, list):
			self.ids = data[:]
			return self.getNextSeries()
		else:
			return self.getAlternativeSeries()

	def getNextSeries(self):
		splog("Wunschliste getNextSeries", self.ids)
		if self.ids:
			id, self.series = self.ids.pop()
			
			if self.when:
				url = EPISODEIDURLATOM + urlencode({ 's' : id })
				data = self.getPageInternal( url )
				return self.getEpisodeFuture( url, data )
			else:
				url = EPISODEIDURLPRINT + urlencode({ 's' : id })
				data = self.getPageInternal( url )
				return self.getEpisodeToday( url, data )
		
		else:
			return ( self.returnvalue or _("No matching series found") )

	def getEpisodeFuture(self, url, data=None):
		splog("Wunschliste getEpisodeFuture")
		
		if data and isinstance(data, basestring):
		#if data and not isinstance(data, WLAtomParser):
			# Handle malformed HTML issues
			data = data.replace('&amp;','&')  # target=\"_blank\"&amp;
			
			parser = WLAtomParser()
			parser.feed(data)
			#splog(parser.list)
			
			data = parser.list
			self.doCache(url, data)
		
		if data:
			trs = data
			if trs:
				yepisode = None
				ydelta = maxint
				
				for tds in trs:
					if tds and len(tds) == 2:
						xtitle, xupdated = tds
						if xtitle is not None and xupdated is not None:
							#import iso8601
							#http://code.google.com/p/pyiso8601/
							xbegin = parse_date(xupdated)
							xbegin = xbegin.replace(tzinfo=None)
							
							#Py2.6
							delta = abs(self.begin - xbegin)
							delta = delta.seconds + delta.days * 24 * 3600
							#Py2.7 delta = abs(self.begin - xbegin).total_seconds()
							splog(self.begin, xbegin, delta, int(config.plugins.seriesplugin.max_time_drift.value)*60)
							
							if delta <= int(config.plugins.seriesplugin.max_time_drift.value) * 60:
								result = CompiledRegexpAtomChannel.search(xtitle)
								if result and len(result.groups()) >= 1:
									
									if compareChannels(self.channels, result.group(1), self.service):
										
										if delta < ydelta:
											# Slice string to remove channel
											xtitle = xtitle[:result.start()]
											result = CompiledRegexpAtomDate.search(xtitle)
											
											if result and len(result.groups()) >= 1:
												# Slice string to remove date
												xtitle = xtitle[:result.start()]
												result = CompiledRegexpAtomEpisode.search(xtitle)
												
												if result and len(result.groups()) >= 1:
													# Extract season and episode
													xepisode = result.group(1)
													# Slice string to remove season and episode
													xtitle = xtitle[:result.start()]
													
													result = CompiledRegexpEpisode.search(xepisode)
													if result and len(result.groups()) >= 3:
														xseason = result and result.group(2) or "1"
														xepisode = result and result.group(3) or "0"
													else:
														splog("Wunschliste wrong episode format", xepisode)
														xseason = "1"
														xepisode = "0"
												else:
													splog("Wunschliste wrong title format", xtitle)
													xseason = "0"
													xepisode = "0"
												result = CompiledRegexpAtomTitle.search(xtitle)
												
												if result and len(result.groups()) >= 1:
													# Extract episode title
													xtitle = result.group(1)
													yepisode = (xseason, xepisode, xtitle.decode('ISO-8859-1').encode('utf8'), self.series.decode('ISO-8859-1').encode('utf8'))
													ydelta = delta
										
										else: #if delta >= ydelta:
											break
									
									else:
										self.returnvalue = _("Check the channel name")
									
							elif yepisode:
								break
				
				if yepisode:
					return ( yepisode )
		
		return self.getNextSeries()

	def getEpisodeToday(self, url, data=None):
		splog("Wunschliste getEpisodeToday")
		
		if data and isinstance(data, basestring):
		#if data and not isinstance(data, WLPrintParser):
		
			# Handle malformed HTML issues
			#data = data.replace('&quot;','&')
			data = data.replace('&amp;','&')
			
			parser = WLPrintParser()
			parser.feed(data)
			#splog(parser.list)
			
			data = parser.list
			self.doCache(url, data)
		
		if data:
			trs = data
			if trs:
				yepisode = None
				ydelta = maxint
				year = str(datetime.today().year)
				
				for tds in trs:
					if tds and len(tds) >= 5:
						#print tds
						xchannel, xday, xdate, xbegin, xend = tds[:5]
						xtitle = "".join(tds[4:])
						xbegin   = datetime.strptime( xdate+year+xbegin, "%d.%m.%Y%H.%M Uhr" )
						#xend     = datetime.strptime( xdate+xend, "%d.%m.%Y%H.%M Uhr" )
						#splog(xchannel, xdate, xbegin, xend, xtitle)
						#splog(datebegin, xbegin, abs((datebegin - xbegin)))
						
						#Py2.6
						delta = abs(self.begin - xbegin)
						delta = delta.seconds + delta.days * 24 * 3600
						#Py2.7 delta = abs(self.begin - xbegin).total_seconds()
						splog(self.begin, xbegin, delta, int(config.plugins.seriesplugin.max_time_drift.value)*60)
						
						if delta <= int(config.plugins.seriesplugin.max_time_drift.value) * 60:
							
							if compareChannels(self.channels, xchannel, self.service):
							
								if delta < ydelta:
									
									print len(tds), tds
									if len(tds) >= 7:
										xepisode, xtitle = tds[5:7]
									
										if xepisode:
											result = CompiledRegexpEpisode.search(xepisode)
											
											if result and len(result.groups()) >= 3:
												xseason = result and result.group(2) or "1"
												xepisode = result and result.group(3) or "0"
											else:
												xseason = "1"
												xepisode = "0"
										else:
											xseason = "1"
											xepisode = "0"
									
									elif len(tds) == 6:
										xtitle = tds[5]
										xseason = "0"
										xepisode = "0"
									
									yepisode = (xseason, xepisode, xtitle.decode('ISO-8859-1').encode('utf8'), self.series.decode('ISO-8859-1').encode('utf8'))
									ydelta = delta
								
								else: #if delta >= ydelta:
									break
							
							else:
								self.returnvalue = _("Check the channel name")
							
						elif yepisode:
							break
				
				if yepisode:
					return ( yepisode )
		
		return self.getNextSeries()

	def getPageInternal(self, url):
		
		if self.checkLicense(url):
			
			# PHP Proxy with 1 day Caching
			# to minimize server requests
			#url = 'http://betonme.lima-city.de/SeriesPlugin/proxy.php?' + urlencode({ 'url' : url })
			#IdentifierBase.getPage(self, url)
			return self.getPage( url)
		
		else:
			return _("No valid license")

	def checkLicense(self, url):
		
		if self.license is not None:
			return self.license
		
		import socket
		socket.setdefaulttimeout(5)
		from urllib import quote_plus
		from urllib2 import urlopen, URLError
		
		try:
			response = urlopen(" http://betonme.lima-city.de/SeriesPlugin/license.php?url="+quote_plus(url) , timeout=5).read()
		except URLError, e:
			raise
			
		print "checkLicense"
		print response
		if response == "Valid License":
			self.license = True
			return True
		else:
			self.license = False
			return False
