#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2017 Joshua Haas <jahschwa.com>
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

from sibyl.lib.protocol import User,Room,Message,Protocol
from sibyl.lib.protocol import ProtocolError as SuperProtocolError
from sibyl.lib.protocol import PingTimeout as SuperPingTimeout
from sibyl.lib.protocol import ConnectFailure as SuperConnectFailure
from sibyl.lib.protocol import AuthFailure as SuperAuthFailure
from sibyl.lib.protocol import ServerShutdown as SuperServerShutdown

from sibyl.lib.decorators import botconf

USER = 'admin@cli'
SIBYL = 'sibyl@cli'

################################################################################
# Custom exceptions
################################################################################

class ProtocolError(SuperProtocolError):
  def __init__(self):
    self.protocol = __name__.split('_')[-1]

class PingTimeout(SuperPingTimeout,ProtocolError):
  pass

class ConnectFailure(SuperConnectFailure,ProtocolError):
  pass

class AuthFailure(SuperAuthFailure,ProtocolError):
  pass

class ServerShutdown(SuperServerShutdown,ProtocolError):
  pass

################################################################################
# Config options
################################################################################

@botconf
def conf(bot):
  return [
    {'name':'log_file','default':'data/stdin.log','valid':bot.conf.valid_wfile}
  ]

################################################################################
# BufferThread class
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
# User sub-class
################################################################################

class Admin(User):

  def parse(self,user):
    self.user = user

  def get_name(self):
    return self.user

  def get_room(self):
    return None

  def get_base(self):
    return self.user

  def __eq__(self,other):
    if not isinstance(other,Admin):
      return False
    return self.user==other.user

  def __str__(self):
    return self.user

################################################################################
# Room sub-class
################################################################################

class FakeRoom(Room):

  def parse(self,name):
    self.name = name

  def get_name(self):
    return self.name

  def __eq__(self,other):
    if not isinstance(other,FakeRoom):
      return False
    return self.name==other.name

################################################################################
# Protocol sub-class
################################################################################

class CLI(Protocol):

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
    self.thread = BufferThread(
        self.queue,self.event_data,self.event_close,self.event_proc)
    self.thread.start()
    self.connected = True

  def is_connected(self):
    return self.connected

  def process(self):

    if not self.event_data.is_set():
      return

    usr = Admin(self,USER)
    text = self.queue.get()

    if self.special_cmds(text):
      return

    msg = Message(usr,text)
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

  def broadcast(self,text,room,frm=None,users=None):
    self.send(text,None)
    return text

  def join_room(self,room):
    self.bot._cb_join_room_failure(room,'not supported')

  def part_room(self,room):
    pass

  def _get_rooms(self,flag):
    return []

  def get_occupants(self,room):
    return []

  def get_nick(self,room):
    return ''

  def get_real(self,room,nick):
    return nick

  def get_user(self):
    return Admin(self,SIBYL)

  def new_user(self,user,typ=None,real=None):
    return Admin(self,user,typ,real)

  def new_room(self,name,nick=None,pword=None):
    return FakeRoom(self,name,nick,pword)

################################################################################

  def special_cmds(self,text):
    """process special admin commands"""

    if not text.startswith('/'):
      return
    args = text[1:].split(' ')
