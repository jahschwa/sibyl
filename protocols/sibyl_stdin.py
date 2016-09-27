#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2016 Joshua Haas <jahschwa.com>
#
# JabberBot: A simple jabber/xmpp bot framework
# Copyright (c) 2007-2012 Thomas Perl <thp.io/about>
# $Id: d1c7090edd754ff0da8ef4eb10d4b46883f34b9f $
#
# This file is part of Sibyl.
#
# Sibyl is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
################################################################################

import sys
from threading import Thread,Event
from Queue import Queue

from lib.protocol import User,Room,Message,Protocol
from lib.protocol import PingTimeout,ConnectFailure,AuthFailure,ServerShutdown

from lib.decorators import botconf

USER = 'admin@std.in'
SIBYL = 'sibyl@std.in'

################################################################################
# Config options                                                               #
################################################################################

@botconf
def conf(bot):
  return [
    {'name':'log_file','default':'data/stdin.log','valid':bot.conf.valid_file}
  ]

################################################################################
# BufferThread class                                                           #
################################################################################

class BufferThread(Thread):

  def __init__(self,q,d,c,p):
    """create a new thread that reads from stdin and appends to a Queue"""

    super(BufferThread,self).__init__()
    self.daemon = True

    self.queue = q
    self.event_data = d
    self.event_close = c
    self.event_proc = p

  def run(self):
    """read from stdin, add to the queue, set the event_data Event"""

    while True:
      self.event_proc.wait()
      if self.event_close.is_set():
        break
      sys.__stdout__.write(USER+': ')
      s = raw_input()
      self.event_proc.clear()
      self.queue.put(s)
      self.event_data.set()

################################################################################
# User sub-class                                                               #
################################################################################

class Admin(User):

  def parse(self,user,typ):
    self.user = user
    self.real = self

  def get_name(self):
    return self.user

  def get_room(self):
    return None

  def get_base(self):
    return self.user

  def __eq__(self,other):
    return isinstance(other,Admin)

  def __str__(self):
    return self.user

################################################################################
# Protocol sub-class                                                           #
################################################################################

class Stdin(Protocol):

  def setup(self):

    self.connected = False
    self.thread = None
    self.proto = 'stdin'

  def connect(self):

    self.queue = Queue()

    self.event_data = Event()
    self.event_close = Event()
    self.event_proc = Event()
    self.event_proc.set()

    sys.__stdout__.write('\n')
    self.thread = BufferThread(self.queue,self.event_data,self.event_close,self.event_proc)
    self.thread.start()
    self.connected = True

  def is_connected(self):
    return self.connected

  def disconnected(self):
    pass

  def process(self,wait=0):

    if not self.event_data.wait(wait):
      return

    usr = Admin(USER,Message.PRIVATE)
    text = self.queue.get()

    if self.special_cmds(text):
      return

    msg = Message(Message.PRIVATE,usr,text)
    self.bot._cb_message(msg)

    if self.queue.empty():
      self.event_data.clear()

    if self.bot._SibylBot__finished:
      self.event_close.set()
    self.event_proc.set()

  def shutdown(self):
    if self.thread:
      self.event_close.set()

  def send(self,text,to):
    if isinstance(text,str):
      text = text.decode('utf')
    text = text.encode(sys.__stdout__.encoding,'replace')
    sys.__stdout__.write(SIBYL+': '+text+'\n')

  def broadcast(self,text,room,frm=None):
    self.send(text,None)

  def join_room(self,room):
    pass

  def part_room(self,room):
    pass

  def in_room(self,room):
    return False

  def get_rooms(self,in_only=False):
    return []

  def get_occupants(self,room):
    return []

  def get_nick(self,room):
    return ''

  def get_real(self,room,nick):
    return Admin(nick,Message.PRIVATE)

  def get_username(self):
    return Admin(SIBYL,Message.PRIVATE)

  def new_user(self,user,typ):
    return Admin(user,typ)

################################################################################

  def special_cmds(self,text):
    """process special admin commands"""
    
    if not text.startswith('/'):
      return
    args = text[1:].split(' ')
