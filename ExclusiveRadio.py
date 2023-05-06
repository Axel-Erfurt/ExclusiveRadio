#!/usr/bin/python3
# -*- coding: utf-8 -*-

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version('Gdk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Gdk, Gst, Notify
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as tray
except:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as tray

import warnings

from gi.repository import GLib
from configparser import ConfigParser
import os
from sys import argv

Gst.init(None)
Gst.init_check(None)

import exclusiveList2

warnings.filterwarnings("ignore")


class RadioPlayer(Gtk.Window):
    def __init__(self, parent=None):
        super(RadioPlayer, self).__init__()

        self.volume = 0.7

        self.audio_sink = Gst.Bin.new('audiosink')

        self.amplify = Gst.ElementFactory.make('audioamplify')
        self.amplify.set_property('amplification', 0.6)
        self.audio_sink.add(self.amplify)

        self.sink = Gst.ElementFactory.make('autoaudiosink')
        self.audio_sink.add(self.sink)

        self.amplify.link(self.sink)
        self.audio_sink.add_pad(Gst.GhostPad.new('sink', self.amplify.get_static_pad('sink')))

        self.player = Gst.ElementFactory.make("playbin", "player")
        self.player.props.audio_sink = self.audio_sink
        self.player.set_property('volume', 0.9)
        
        ### Listen for metadata
        self.bus = self.player.get_bus()
        self.bus.enable_sync_message_emission()
        self.bus.add_signal_watch()
        self.bus.connect('message::tag', self.on_tag)

        self.connect("destroy",Gtk.main_quit)

        self.channel = 0
        self.title = ''
        self.url = ''
        self.station = ''
        self.old_tag = ''
        self.my_icon = f'{os.path.dirname(os.path.abspath(argv[0]))}/icon_128.png'
        self.my_menu_icon = f'{os.path.dirname(os.path.abspath(argv[0]))}/icon_20.png'
        Notify.init("Welcome to \nExclusive Radio")

        ### Radio List
        self.chlist = self.radioList().splitlines()
        self.ch_names = []
        self.ch_urls = []
        
        ### System Tray Icon
        self.indicator = tray.Indicator.new("Exclusive Radio Tray", self.my_icon, tray.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(tray.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.create_menu())
        self.indicator.connect("scroll-event", self.scroll_notify_event)
        
        ### Handle song metadata
    def on_tag(self, bus, msg):
        taglist = msg.parse_tag()
        my_tag = f'{taglist.get_string(taglist.nth_tag_name(0)).value}'
        if not self.old_tag == my_tag and not "Exclusively" in my_tag:
            print(my_tag)
            self.showNotification(my_tag)
            self.old_tag = my_tag
        
    def showNotification(self, message, *args):
        n = Notify.Notification.new("Exclusive Radio", message, self.my_icon)
        n.set_timeout(5000)
        n.show()
    
    def scroll_notify_event(self, ind, steps, e):
        vol = self.amplify.get_property('amplification')
        if e == Gdk.ScrollDirection.UP:
            if vol < 1.0:
                self.amplify.set_property('amplification', vol + 0.05)
        elif e == Gdk.ScrollDirection.DOWN:
            if vol > 0.0:
                self.amplify.set_property('amplification', vol - 0.05)
        new_vol = format(self.amplify.get_property("amplification"), '.2f') 
        print(f'Volume changed to {str(new_vol)}')
        self.volume = new_vol


    def item_activated(self, wdg, i):
        print(f"Station: {self.ch_names[i]}")
        self.station = self.ch_names[i]
        self.url = self.ch_urls[i]
        self.playStation(self.url)
        
    def stopPlayer(self, *args):
        self.player.set_state(Gst.State.NULL)
        
    def create_menu(self):
        i = 0
        self.tray_menu = Gtk.Menu()
        
        img = Gtk.Image()
        img.set_from_icon_name("media-playback-stop", 20)
        self.action_stop = Gtk.ImageMenuItem.new_with_label("Stop")
        self.action_stop.set_image(img)
        self.action_stop.connect("activate", self.stopPlayer)
        self.tray_menu.append(self.action_stop)
        
        sep = Gtk.SeparatorMenuItem()
        self.tray_menu.append(sep)
        
        img = Gtk.Image()
        img.set_from_icon_name("application-exit", 20)
        self.action_filequit = Gtk.ImageMenuItem.new_with_label("Quit")
        self.action_filequit.set_image(img)
        self.action_filequit.connect("activate", self.handleClose)
        self.tray_menu.append(self.action_filequit)
        
        sep_menu = Gtk.SeparatorMenuItem()
        self.tray_menu.append(sep_menu)

        b = self.chlist
        i = 0
        for x in range(len(self.chlist)):
            while True:
                if b[x].startswith("--"):
                    img = Gtk.Image()
                    img.set_from_file(self.my_menu_icon)
                    self.sub1 = Gtk.ImageMenuItem.new_with_label(b[x].replace("-- ", "").replace(" --", ""))
                    self.sub1.set_image(img)
                    self.tray_menu.append(self.sub1)
                    self.submenu1 = Gtk.Menu()
                    break
                    continue
                    
                if not b[x].startswith("--"):
                    name = b[x].partition(",")[0]
                    ch = b[x].partition(",")[2]
                    self.ch_names.append(name)
                    self.ch_urls.append(ch)
                    action_channel = Gtk.ImageMenuItem.new_with_label(name)
                    img = Gtk.Image()
                    img.set_from_file(self.my_menu_icon)
                    self.submenu1.append(action_channel)
                    action_channel.set_image(img)
                    action_channel.connect("activate", self.item_activated, i)
                    self.sub1.set_submenu(self.submenu1)
                    i += 1
                    break
        
        self.tray_menu.show_all()
        return self.tray_menu


    def handleClose(self, *args):
        self.showNotification("Goodbye ...")
        self.writeSettings()
        Gtk.main_quit()

    def playStation(self, url, *args):
        self.player.set_state(Gst.State.NULL)
        self.player.set_property("uri", url)
        self.player.set_property("buffer-size", 2*1048576) # 2MB
        self.player.set_state(Gst.State.PLAYING)
        print(self.player.get_metadata("Icy-MetaData"))

        
    def radioList(self):
        radiolist = exclusiveList2.ex_list
        return radiolist
            
    def readSettings(self, *args):
        print("reading settings")
        parser = ConfigParser()
        confDir =  os.path.join(GLib.get_user_config_dir(), 'ExclusiveRadio/')
        confFile = os.path.join(confDir + "conf.ini")
        if os.path.exists(confFile):
            parser.read(confFile)            
            self.volume = float(parser.get('Preferences', 'radio_volume'))
            self.url = parser.get('Preferences', 'last_channel')
            print(f'Volume set to {self.volume}\nplaying last Channel {self.url}')
            self.amplify.set_property('amplification', self.volume)
            if not self.url == '':
                self.playStation(self.url)

            
    def writeSettings(self):
        print("writing settings")
        confDir =  os.path.join(GLib.get_user_config_dir(), 'ExclusiveRadio/')
        confFile = os.path.join(confDir + "conf.ini")
        config = ConfigParser()

        if not os.path.exists(confDir):
            os.makedirs(confDir)
        config.add_section('Preferences')
        config.set('Preferences', 'radio_volume', str(self.volume))
        config.set('Preferences', 'last_channel', self.url)
        with open(confFile, 'w') as confFile:
            config.write(confFile)


win = RadioPlayer()
print("Welcome to Exclusive Radio")
win.showNotification(f"Welcome to Exclusive Radio")
win.readSettings()
Gtk.main()
