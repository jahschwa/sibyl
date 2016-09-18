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

from lib.protocol import User,Message,Protocol
from lib.protocol import PingTimeout,ConnectFailure,AuthFailure,ServerShutdown

from lib.decorators import botconf

################################################################################
# Config options                                                               #
################################################################################

@botconf
def conf(bot):
  return [
    {'name':'stdin_log','default':'data/stdin.log','valid':bot.conf.valid_file}
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
      sys.__stdout__.write('admin@std.in: ')
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

  def process(self):

    if not self.event_data.wait(1):
      return

    rule = ('w','admin@std.in','*')
    if self.bot.opt('bw_list')[-1]!=rule:
      self.bot.conf.opts['bw_list'].append(rule)

    usr = Admin('admin@std.in',Message.PRIVATE)
    msg = Message(Message.PRIVATE,usr,self.queue.get())
    self.bot._cb_message(msg)

    if self.queue.empty():
      self.event_data.clear()

    if self.bot._SibylBot__finished:
      self.event_close.set()
    self.event_proc.set()

  def shutdown(self):
    if self.thread:
      self.event_close.set()
      self.thread.join()

  def send(self,text,to):
    sys.__stdout__.write('sibyl@std.in: '+text+'\n')

  def broadcast(self,text,room,frm=None):
    self.send(text,None)

  def join_room(self,room,nick,pword=None):
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
    return 'root'

  def get_real(self,room,nick):
    return Admin(nick,Message.PRIVATE)

  def new_user(self,user,typ):
    return Admin(user,typ)

