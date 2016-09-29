#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2016 Joshua Haas <jahschwa.com>
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

import socket,select,errno,time
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
    {'name':'port','default':8767},
    {'name':'internet','default':False,'parse':bot.conf.parse_bool}
  ]

################################################################################
# ServerThread class                                                           #
################################################################################

class ServerThread(Thread):

  def __init__(self,log,q,d,c):
    """create a new thread that handles socket connections"""

    super(ServerThread,self).__init__()
    self.daemon = True

    self.log = log
    self.queue = q
    self.event_data = d
    self.event_close = c

    self.dead = Queue()
    self.clients = {}
    self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)

  def bind(self,hostname,port):
    """bind our server socket"""

    self.socket.bind((hostname,port))
    self.socket.listen(5)

  def run(self):
    """accept incoming connections and spawn clients"""

    while True:

      if self.event_close.is_set():
        break
      (read,write,err) = select.select([self.socket],[],[],1)

      if self.socket in read:
        (conn,address) = self.socket.accept()
        self.log.info('Got new connection from %s:%s' % address)
        q = Queue()
        self.clients[address] = q
        ipc = {'rq':self.queue,'sq':q,'ed':self.event_data,'ec':self.event_close}
        ClientThread(self,conn,address,ipc).start()

      while not self.dead.empty():
        client = self.dead.get()
        del self.clients[client]
        self.log.info('Remote closed connection %s:%s@socket' % client)

      time.sleep(0.1)

    self.socket.close()

  def send(self,text,address):
    """queue a message to be sent"""

    try:
      self.clients[address].put(text)
    except KeyError:
      self.log.warning('Attempted to send a message to a disconnected client')

################################################################################
# ClientThread class                                                           #
################################################################################

class ClientThread(Thread):

  def __init__(self,srv,conn,addr,ipc):

    """cretae a new thread that handles client connections"""

    super(ClientThread,self).__init__()
    self.daemon = True

    self.server = srv
    self.socket = conn
    self.address = addr
    self.ipc = ipc

    self.buffer = ''

  def run(self):
    """receive and send data on the socket"""

    while not self.ipc['ec'].is_set():
      (read,write,err) = select.select([self.socket],[self.socket],[],1)

      if self.socket in read:
        try:
          msgs = self.get_msgs()
        except:
          break
        if msgs:
          self.ipc['ed'].set()
        for msg in msgs:
          if msg:
            self.ipc['rq'].put((self.address,msg))

      if self.socket in write:
        while not self.ipc['sq'].empty():
          self.send_msg(self.ipc['sq'].get())

      time.sleep(0.1)

    self.server.dead.put(self.address)
    self.socket.close()

  def get_msgs(self):

    msgs = []
    while self.buffer or not msgs:
      msgs.append(self.get_msg())
    return msgs

  def get_msg(self):

    msg = self.buffer
    while ' ' not in msg:
      s = self.socket.recv(4096)
      if not s:
        raise RuntimeError
      msg += s

    length_str = msg.split(' ')[0]
    target = len(length_str)+1+int(length_str)
    while len(msg)<target:
      msg += self.socket.recv(min(target-len(msg),4096))

    self.buffer = msg[target:]
    return msg[msg.find(' ')+1:]

  def send_msg(self,msg):

    length_str = str(len(msg))
    msg = (length_str+' '+msg)
    target = len(msg)

    sent = 0
    while sent<target:
      sent += self.socket.send(msg[sent:])

################################################################################
# User sub-class                                                               #
################################################################################

class Client(User):

  def parse(self,info,typ):
    self.address = info
    self.user = '%s:%s@socket' % info
    self.real = self

  def get_name(self):
    return self.user

  def get_room(self):
    return None

  def get_base(self):
    return self.user

  def __eq__(self,other):
    if not isinstance(Client,other):
      return False
    return self.address==other.address

  def __str__(self):
    return self.user

################################################################################
# Protocol sub-class                                                           #
################################################################################

class SocketServer(Protocol):

  def setup(self):

    self.connected = False
    self.thread = None

  def connect(self):

    q = Queue()
    if hasattr(self,'queue'):
      for x in self.queue.queue:
        q.put(x)
    self.queue = q
    self.event_data = Event()
    if not self.queue.empty():
      self.event_data.set()
    self.event_close = Event()

    hostname = 'localhost'
    if self.opt('socket.internet'):
      hostname = socket.gethostname()
    port = self.opt('socket.port')
    self.thread = ServerThread(self.log,self.queue,self.event_data,self.event_close)

    self.log.info('Attempting to bind to %s:%s' % (hostname,port))
    try:
      self.thread.bind(hostname,port)
    except Exception as e:
      if e.errno==errno.EACCES:
        self.log.error('Unable to bind (permission denied)' % (hostname,port))
        raise AuthFailure
      else:
        n = e.errno
        self.log.error('Unhandled error %s = %s' % (n,errno.errorcode[n]))
        raise AuthFailure

    self.thread.start()
    self.connected = True

  def is_connected(self):
    return self.connected

  def disconnected(self):
    self.connected = False

  def process(self,wait=0):

    if not self.event_data.wait(wait):
      return

    (address,text) = self.queue.get()
    usr = Client(address,Message.PRIVATE)

    if self.special_cmds(text):
      return

    msg = Message(Message.PRIVATE,usr,text)
    self.bot._cb_message(msg)

    if self.queue.empty():
      self.event_data.clear()

  def shutdown(self):
    self.event_close.set()
    self.thread.join()

  def send(self,text,to):
    self.thread.send(text,to.address)

  def broadcast(self,text,room,frm=None):
    pass

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
    return 'sibyl'

  def get_real(self,room,nick):
    return nick

  def get_username(self):
    return Client((0,'sibyl@socket'),Message.PRIVATE)

  def new_user(self,user,typ):
    return Client((time.time(),user),typ)

################################################################################

  def special_cmds(self,text):
    """process special admin commands"""
    
    if not text.startswith('/'):
      return
    args = text[1:].split(' ')
