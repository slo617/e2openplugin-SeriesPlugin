# -*- coding: utf-8 -*-
from __init__ import _

from Components.ActionMap import ActionMap, HelpableActionMap
#from Components.Label import Label
from Components.MenuList import MenuList
#from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmap, MultiContentEntryPixmapAlphaTest
#from Tools.LoadPixmap import LoadPixmap
#from Components.Pixmap import Pixmap
#from Components.AVSwitch import AVSwitch
#from Screens.InfoBar import MoviePlayer
#from Components.PluginComponent import plugins
from Components.Button import Button
from Screens.Screen import Screen
#from Plugins.Plugin import PluginDescriptor
#from twisted.web.client import getPage
#from twisted.web.client import downloadPage

#from Components.ServicePosition import ServicePositionGauge
#from Tools.NumericalTextInput import NumericalTextInput
from Tools.BoundFunction import boundFunction
#from Components.ConfigList import ConfigList, ConfigListScreen
from Components.config import config

#from Components.ScrollLabel import ScrollLabel
#from Components.FileList import FileList
#from Components.Sources.StaticText import StaticText

from Screens.HelpMenu import HelpableScreen
#from Screens.InputBox import InputBox
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
#from Screens.Standby import TryQuitMainloop
#from Screens.VirtualKeyBoard import VirtualKeyBoard

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, loadPNG, RT_WRAP, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_VALIGN_BOTTOM
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
import sys, os, base64, re, time, shutil, datetime, codecs, urllib2
from twisted.web import client, error as weberror
from twisted.internet import reactor, defer
from urllib import urlencode
from skin import parseColor

#from Screens.ChannelSelection import service_types_tv
#from ServiceReference import ServiceReference

#from Components.UsageConfig import preferredTimerPath, preferredInstantRecordPath

# Navigation (RecordTimer)
#import NavigationInstance

# Timer
#from RecordTimer import RecordTimerEntry, RecordTimer, parseEvent, AFTEREVENT
#from Components.TimerSanityCheck import TimerSanityCheck

# EPGCache & Event
#from enigma import eEPGCache, iServiceInformation

#from Tools import Notifications

#Internal
from Channels import ChannelsBase, buildSTBchannellist, unifyChannel
from Logger import splog


# Constants
PIXMAP_PATH = os.path.join( resolveFilename(SCOPE_PLUGINS), "Extensions/SeriesPlugin/Images/" )

colorRed    = 0xf23d21
colorGreen  = 0x389416
colorBlue   = 0x0064c7
colorYellow = 0xbab329
colorWhite  = 0xffffff


class ChannelEditor(Screen, HelpableScreen, ChannelsBase):
	
	skinfile = os.path.join( resolveFilename(SCOPE_PLUGINS), "Extensions/SeriesPlugin/skinChannelEditor.xml" )
	skin = open(skinfile).read()
	
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		ChannelsBase.__init__(self)
		
		self.session = session
		
		self.skinName = [ "SeriesPluginChannelEditor" ]
		
		from plugin import NAME, VERSION
		self.setup_title = NAME + " " + _("Channel Editor") + " " + VERSION
		
		# Buttons
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))
		self["key_blue"] = Button(_("Remove"))
		self["key_yellow"] = Button(_("Reset"))
		
		# Define Actions
		self["actions_1"] = HelpableActionMap(self, "SetupActions", {
			"ok"       : (self.keyAdd, _("Show popup to add Stb Channel")),
			"cancel"   : (self.keyCancel, _("Cancel and close")),
		}, -1)
		self["actions_2"] = HelpableActionMap(self, "DirectionActions", {
			"left"     : (self.keyLeft, _("Previeous page")),
			"right"    : (self.keyRight, _("Next page")),
			"up"       : (self.keyUp, _("One row up")),
			"down"     : (self.keyDown, _("One row down")),
		}, -1)
		self["actions_3"] = HelpableActionMap(self, "ColorActions", {
			"red"      : (self.keyCancel, _("Cancel and close")),
			"green"    : (self.keySave, _("Save and close")),
			"blue"     : (self.keyRemove, _("Remove channel")),
			"yellow"   : (self.keyResetChannelMapping, _("Reset channels")),
		}, -2) # higher priority
		
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["HelpActions",], {
			"displayHelp"      : self.showHelp
		}, 0)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 ))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['list'].show()

		self.stbChlist = []
		self.webChlist = []
		self.stbToWebChlist = []
		
		self.onLayoutFinish.append(self.readChannels)

	def readChannels(self):
		self.setTitle(_("Load Web-Channels..."))
		
		self.stbToWebChlist = []
		
		if not self.stbChlist:
			self.stbChlist = buildSTBchannellist(config.plugins.seriesplugin.bouquet_main.value)
		
		if not self.webChlist:
			from WebChannels import WebChannels
			WebChannels(self.setWebChannels).request()
		else:
			self.showChannels()

	def setWebChannels(self, data):
		self.webChlist = data
		self.showChannels()

	def showChannels(self):
		#self.webChlist.sort(key=lambda x: x.lower())
		if len(self.stbChlist) != 0:
			for servicename,serviceref in self.stbChlist:
				splog("SPC: servicename", servicename)
				
				webSender = self.lookupChannelByReference(serviceref)
				if webSender:
					self.stbToWebChlist.append((servicename, webSender, serviceref, "1"))
					
				else:
					if len(self.webChlist) != 0:
						for webSender in self.webChlist:
							if re.search("\A%s\Z" % webSender.lower().replace('+','\+').replace('.','\.'), servicename.lower(), re.S):
								self.stbToWebChlist.append((servicename, webSender, serviceref, "1"))
								uremote = unifyChannel(webSender)
								self.addChannel(serviceref, servicename, webSender, uremote)
								break
						else:
							self.stbToWebChlist.append((servicename, "", serviceref, "0"))
					else:
						self.stbToWebChlist.append((servicename, "", serviceref, "0"))
		if len(self.stbToWebChlist) != 0:
			self.chooseMenuList.setList(map(self.buildList, self.stbToWebChlist))
		else:
			splog("SPC: Error creating webChlist..")
			self.setTitle(_("Error check log file"))
		
	def buildList(self, entry):
		self.setTitle(_("Web-Channel / STB-Channels."))
		
		(stbSender, webSender, serviceref, status) = entry
		if int(status) == 0:		
			imageStatus = path = os.path.join(PIXMAP_PATH, "minus.png")
		else:
			imageStatus = path = os.path.join(PIXMAP_PATH, "plus.png")
			
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 8, 16, 16, loadPNG(imageStatus)),
			(eListboxPythonMultiContent.TYPE_TEXT, 35, 3, 300, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, stbSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 350, 3, 250, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 600, 3, 250, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "", colorYellow)
			]

	def keyAdd(self):
		check = self['list'].getCurrent()
		if check == None:
			splog("SPC: list empty")
			return
		else:
			idx = 0
			#webSender = self['list'].getCurrent()[0][1]
			(servicename, webSender, serviceref, state) = self['list'].getCurrent()[0]
			splog("keyAdd webSender", webSender)
			idx = 0
			if webSender:
				try:
					idx = self.webChlist.index(webSender)
				except:
					idx = 0
			list = [(x,x) for x in self.webChlist]
			self.session.openWithCallback( boundFunction(self.addConfirm, servicename, serviceref), ChoiceBox,_("Add Web Channel"), list, None, idx)

	def addConfirm(self, servicename, serviceref, result):
		if result:
			remote = result[0]
			#serviceref = self['list'].getCurrent()[0][2]
			#servicename = self['list'].getCurrent()[0][0]
			uremote = unifyChannel(remote)
			splog("addConfirm", servicename, serviceref, remote)
			if servicename and serviceref and remote and uremote:
				self.addChannel(serviceref, servicename, remote, uremote)
				self.setTitle(_("Channel '- %s - %s -' added.") % (servicename, remote) )
				self.readChannels()

	def keyRemove(self):
		check = self['list'].getCurrent()
		if check == None:
			splog("SPC: list empty")
			return
		else:
			(servicename, webSender, serviceref, state) = self['list'].getCurrent()[0]
			self.session.openWithCallback( boundFunction(self.removeConfirm, servicename, serviceref), MessageBox, _("Remove '%s'?") % servicename, MessageBox.TYPE_YESNO, default = False)

	def removeConfirm(self, servicename, serviceref, answer):
		if not answer:
			return
		if serviceref:
			self.removeChannel(serviceref)
			self.setTitle(_("Channel '- %s -' removed.") % servicename)
			self.readChannels()

	def keyResetChannelMapping(self):
		self.session.openWithCallback(self.channelReset, MessageBox, _("Reset channel list?"), MessageBox.TYPE_YESNO)

	def channelReset(self, answer):
		if answer:
			splog("SPC: channel-list reset...")
			self.resetChannels()
			self.stbChlist = []
			self.webChlist = []
			self.stbToWebChlist = []
			self.readChannels()

	def keyLeft(self):
		self['list'].pageUp()

	def keyRight(self):
		self['list'].pageDown()

	def keyDown(self):
		self['list'].down()

	def keyUp(self):
		self['list'].up()
	
	def keySave(self):
		self.close(ChannelsBase.channels_changed)

	def keyCancel(self):
		self.close(False)

	def hideHelpWindow(self):
		current = self["config"].getCurrent()
		if current and hasattr(current[1], "help_window"):
			help_window = current[1].help_window
			if help_window:
				help_window.hide()
