# by betonme @2012
#
#########################################
#
# !! Never make this file public !!
#
#########################################

import math
from sys import maxint

from Components.config import config
from Tools.BoundFunction import boundFunction

# Imports
from urllib import urlencode

#from HTMLParser import HTMLParser
from bs4 import BeautifulSoup

from time import time
from datetime import datetime, timedelta

import json

# Internal
from Plugins.Extensions.SeriesPlugin.IdentifierBase import IdentifierBase
from Plugins.Extensions.SeriesPlugin.Channels import compareChannels
from Plugins.Extensions.SeriesPlugin.Logger import splog


# Constants
SERIESLISTURL = "http://www.fernsehserien.de/suche?"
EPISODEIDURL = 'http://www.fernsehserien.de%s/sendetermine/%d'

max_time_drift = int(config.plugins.seriesplugin.max_time_drift.value) * 60

Headers = {
		'User-Agent' : 'Mozilla/5.0',
		'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Charset':'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
		'Accept-Encoding':'',
		'Accept-Language':'de-DE,de;q=0.8,en-US;q=0.6,en;q=0.4',
		'Cache-Control':'no-cache',
		'Connection':'keep-alive',
		'Host':'www.fernsehserien.de',
		'Pragma':'no-cache'
	}


class Fernsehserien(IdentifierBase):
	def __init__(self):
		IdentifierBase.__init__(self)
		self.id = 0
		self.page = 0

	@classmethod
	def knowsElapsed(cls):
		return True

	@classmethod
	def knowsToday(cls):
		return True

	@classmethod
	def knowsFuture(cls):
		return True

	def getEpisode(self, name, begin, end=None, service=None, channels=[]):
		# On Success: Return a single season, episode, title tuple
		# On Failure: Return a empty list or None
		
		self.license = None
		
		self.name = name
		self.begin = begin
		#self.year = datetime.fromtimestamp(begin).year
		self.end = end
		self.service = service
		self.channels = channels
		self.ids = []
		
		self.soup = None
		
		self.id = 0
		self.series = ""
		self.first = None
		self.last = None
		self.page = 0
		
		self.returnvalue = None
		
		# Check preconditions
		if not name:
			splog(_("Skip Fernsehserien: No show name specified"))
			return _("Skip Fernsehserien: No show name specified")
		if not begin:
			splog(_("Skip Fernsehserien: No begin timestamp specified"))
			return _("Skip Fernsehserien: No begin timestamp specified")
		
		if self.begin > datetime.now():
			self.future = True
		else:
			self.future = False
		
		splog("Fernsehserien getEpisode future", self.future)
		return self.getSeries()

	def getAlternativeSeries(self):
		self.name = " ".join(self.name.split(" ")[:-1])
		if self.name:
			return self.getSeries()
		else:
			return ( self.returnvalue or _("No matching series found") )
	
	def getSeries(self):
		url = SERIESLISTURL + urlencode({ 'term' : self.name })
		data = self.getPageInternal( url )

		serieslist = []
		
		if data and isinstance(data, basestring):
			for line in json.loads(data):
				id = line['id']
				idname = line['value']
				splog(id, idname)
				serieslist.append( (id, idname) )
			serieslist.reverse()
			
			data = serieslist
			self.doCache(url, data)
		
		if data and isinstance(data, list):
			self.ids = data[:]
			return self.getNextSeries()
		else:
			return self.getAlternativeSeries()

	def getNextSeries(self):
		splog("Fernsehserien getNextSeries", self.ids)
		if self.ids:
			self.id, self.series = self.ids.pop()
			
			self.page = 0
			#if self.future:
			#	self.page = 0
			#else:
			#	self.page = -1
			
			self.first = None
			self.last = None
			
			return self.getNextPage()
		
		else:
			return ( self.returnvalue or _("No matching series found") )

	def getNextPage(self):
		url = EPISODEIDURL % (self.id, self.page)
		data = self.getPageInternal( url )
		
		trs = []
		
		if data and isinstance(data, basestring):
			
			# Handle malformed HTML issues
			data = data.replace('\\"','"')  # target=\"_blank\"
			data = data.replace('\'+\'','') # document.write('<scr'+'ipt
			
			self.soup = BeautifulSoup(data)
			
			table = self.soup.find('table', 'sendetermine')
			if table:
				for trnode in table.find_all('tr'):
					# TODO skip first header row
					tdnodes = trnode and trnode.find_all('td')
					
					if tdnodes:
						# Filter for known rows
						#if len(tdnodes) == 7 and len(tdnodes[2].string) >= 15:
						
						if len(tdnodes) >= 6 and tdnodes[2].string and len(tdnodes[2].string) >= 15:
							tds = []
							for tdnode in tdnodes:
								tds.append(tdnode.string or "")
							trs.append( tds )
						# This row belongs to the previous
						elif trs and len(tdnodes) == 5:
							#if trs[-1][5] and tdnodes[3].string:
							trs[-1][5] += ' ' + (tdnodes[3].string or "")
							#if trs[-1][6] and tdnodes[4].string:
							trs[-1][6] += ' ' + (tdnodes[4].string or "")
						else:
							splog( "tdnodes", len(tdnodes), tdnodes )
					
					else:
						splog( "tdnodes", tdnodes )
			
			splog(trs)
			
			data = trs
			self.doCache(url, data)
		
		if data:
			
			trs = data
			# trs[x] = [None, u'31.10.2012', u'20:15\u201321:15 Uhr', u'ProSieben', u'8.', u'15', u'Richtungswechsel']
			if not trs:
				pass
			
			else:
				yepisode = None
				ydelta = maxint
				
				first = trs[0][2]
				last = trs[-1][2]
				
				#print first[0:5]
				#print last[6:11] 
				
				# trs[0] first line [2] second element = timestamps [a:b] use first time
				first = datetime.strptime( first[0:5] + trs[0][1], "%H:%M%d.%m.%Y" )
				# trs[-1] last line [2] second element = timestamps [a:b] use second time
				last = datetime.strptime( last[6:11] + trs[-1][1], "%H:%M%d.%m.%Y" )
				
				first = first - timedelta(seconds=max_time_drift)
				last = last + timedelta(seconds=max_time_drift)
				
				if self.first != first and self.last != last:
					self.first = first
					self.last = last
					
					splog("first, self.begin, last, if ", first, self.begin, last, ( first <= self.begin and self.begin <= last ))
					if ( first <= self.begin and self.begin <= last ):
						#search in page for matching datetime
						for tds in trs:
							if tds and len(tds) >= 6:  #7:
								# Grey's Anathomy
								# [None, u'31.10.2012', u'20:15\u201321:15 Uhr', u'ProSieben', u'8.', u'15', u'Richtungswechsel']
								# 
								# Gute Zeiten 
								# [None, u'20.11.2012', u'06:40\u201307:20 Uhr', u'NDR', None, u'4187', u'Folge 4187']
								# [None, u'01.12.2012', u'10:45\u201313:15 Uhr', u'RTL', None, u'5131', u'Folge 5131']
								# [None, u'\xa0', None, u'5132', u'Folge 5132']
								# [None, u'\xa0', None, u'5133', u'Folge 5133']
								# [None, u'\xa0', None, u'5134', u'Folge 5134']
								# [None, u'\xa0', None, u'5135', u'Folge 5135']
								
								# Wahnfried
								# [u'Sa', u'26.12.1987', u'\u2013', u'So', u'27.12.1987', u'1Plus', None]
								
								# First part: date, times, channel
								xdate, xbegin = tds[1:3]
								splog( "tds", tds )
								
								#xend = xbegin[6:11]
								xbegin = xbegin[0:5]
								xbegin = datetime.strptime( xbegin+xdate, "%H:%M%d.%m.%Y" )
								#xend = datetime.strptime( xend+xdate, "%H:%M%d.%m.%Y" )
								#print "xbegin", xbegin
								
								#Py2.6
								delta = abs(self.begin - xbegin)
								delta = delta.seconds + delta.days * 24 * 3600
								#Py2.7 delta = abs(self.begin - xbegin).total_seconds()
								splog(self.begin, xbegin, delta, max_time_drift)
								
								if delta <= max_time_drift:
									
									if compareChannels(self.channels, tds[3], self.service):
										
										if delta < ydelta:
											
											splog( "tds", len(tds), tds )
											if len(tds) >= 10:
												# Second part: s1e1, s1e2,
												xseason = tds[7] or "1"
												xepisode = tds[8]
												xtitle = " ".join(tds[10:])  # Use all available titles
											elif len(tds) >= 7:
												# Second part: s1e1, s1e2,
												xseason = tds[4]
												xepisode = tds[5]
												if xseason and xseason.find(".") != -1:
													xseason = xseason[:-1]
													xtitle = " ".join(tds[6:])  # Use all available titles
												else:
													xseason = "1"
													xtitle = " ".join(tds[6:])  # Use all available titles
											elif len(tds) == 6:
												xseason = "0"
												xepisode = "0"
												xtitle = tds[5]
											if xseason and xepisode and xtitle and self.series:
												yepisode = (xseason, xepisode, xtitle, self.series)
												ydelta = delta
										
										else: #if delta >= ydelta:
											break
									
									else:
										self.returnvalue = _("Check the channel name")
									
								elif yepisode:
									break
						
						if yepisode:
							return ( yepisode )
					
					else:
						#calculate next page : use firstrow lastrow datetime
						if not self.future:
							if first > self.begin:
								self.page -= 1
								return self.getNextPage()
						
						else:
							if self.begin > last:
								self.page += 1
								return self.getNextPage()
		
		return self.getNextSeries()

	def getPageInternal(self, url):
		
		if self.checkLicense(url):
		
			# PHP Proxy with 1 day Caching
			# to minimize server requests
			#url = 'http://betonme.lima-city.de/SeriesPlugin/proxy.php?' + urlencode({ 'url' : url })
			#IdentifierBase.getPage(self, url, Headers)
			return self.getPage(url, Headers)
			
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
			response = urlopen("http://betonme.lima-city.de/SeriesPlugin/license.php?url="+quote_plus(url) , timeout=5).read()
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
