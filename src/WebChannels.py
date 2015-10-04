# -*- coding: utf-8 -*-
from __init__ import _

import re

from twisted.web.client import getPage
from twisted.internet import defer

import socket
from urllib import urlencode
from urllib2 import urlopen, Request, URLError

from Components.config import config

import HTMLParser
#html_parser = HTMLParser.HTMLParser()


#from SerienRecorder import getUserAgent
import datetime, random
def getUserAgent():
	userAgents = [
	    "Mozilla/5.0"
	]
	today = datetime.date.today()
	random.seed(today.toordinal())
	#return userAgents[random.randint(0, 8)]
	return userAgents[0]

def iso8859_Decode(txt):
	txt = unicode(txt, 'ISO-8859-1')
	txt = txt.encode('utf-8')
	txt = txt.replace('...','').replace('..','').replace(':','')

	# &apos;, &quot;, &amp;, &lt;, and &gt;
	txt = txt.replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"')
	#txt = html_parser.unescape(txt)
	return txt


class WebChannels(object):
	def __init__(self, user_callback=None, user_errback=None):
		self.user_callback = user_callback
		self.user_errback  = user_errback

	def	request(self):
		print "[SP] request webpage.."
		url = "http://www.wunschliste.de/updates/stationen"
		#getPage(url, agent="Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0", headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.__callback).addErrback(self.__errback)
		getPage(url, agent=getUserAgent(), headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.__callback).addErrback(self.__errback)

	def request_and_return(self):
		print "[SP] request_and_return webpage.."
		url = "http://www.wunschliste.de/updates/stationen"
		req = Request(url, headers={'Content-Type':'application/x-www-form-urlencoded'})
		try:
			data = urlopen(req).read()
		except URLError as e:
			self.__errback(str(e))
		except socket.timeout as e:
			self.__errback(str(e))
		return self.__callback(data)

	def __errback(self, error):
		print error
		if (self.user_errback):
			self.user_errback(error)

	def __callback(self, data):
		#from SP import iso8859_Decode
		stations = re.findall('<option value=".*?>(.*?)</option>', data, re.S)
		if stations:
			web_chlist = []
			for station in stations:
				if station != 'alle':
					station = iso8859_Decode(station)
					station = station.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (&Ouml;sterreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').replace('&#x1f512;','')
					#station = station.strip()
					
					web_chlist.append(station)

		if (self.user_callback):
			self.user_callback(web_chlist)
		
		#web_chlist.sort()
		
		return web_chlist
