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

import socket,select,errno,time,traceback
from threading import Thread,Event
from Queue import Queue

from sibyl.lib.protocol import User,Room,Message,Protocol
from sibyl.lib.protocol import ProtocolError as SuperProtocolError
from sibyl.lib.protocol import PingTimeout as SuperPingTimeout
from sibyl.lib.protocol import ConnectFailure as SuperConnectFailure
from sibyl.lib.protocol import AuthFailure as SuperAuthFailure
from sibyl.lib.protocol import ServerShutdown as SuperServerShutdown

from sibyl.lib.decorators import botconf

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
    {'name':'port','default':8767},
    {'name':'password'},
    {'name':'pubkey','valid':bot.conf.valid_rfile},
    {'name':'privkey','valid':bot.conf.valid_rfile},
    {'name':'key_password'},
    {'name':'internet','default':False,'parse':bot.conf.parse_bool}
  ]

################################################################################
# ServerThread class
################################################################################

class ServerThread(Thread):

  def __init__(self,log,q,d,c,pword=None,ssl=None):
    """create a new thread that handles socket connections"""

    super(ServerThread,self).__init__()
    self.daemon = True

    self.log = log
    self.queue = q
    self.event_data = d
    self.event_close = c
    self.password = pword
    self.context = ssl

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

        try:
          if self.context:
            conn = self.context.wrap_socket(conn,server_side=True)
          self.log.info('Got new connection from %s:%s' % address)
          q = Queue()
          self.clients[address] = q
          ipc = {'rq':self.queue,'sq':q,
                  'ed':self.event_data,'ec':self.event_close}
          ClientThread(self,conn,address,ipc).start()
        except Exception as e:
          self.log.warning('New connection %s:%s failed (%s)' %
              (address+(e.__class__.__name__,)))
          try:
            conn.shutdown(socket.SHUT_RDWR)
          except:
            pass
          conn.close()

      while not self.dead.empty():
        client = self.dead.get()
        del self.clients[client]
        self.log.info('Connection closed %s:%s@socket' % client)

      time.sleep(0.1)

    self.socket.close()

  def send(self,text,address):
    """queue a message to be sent"""

    try:
      self.clients[address].put(text)
    except KeyError:
      self.log.warning('Attempted to send a message to a disconnected client')

################################################################################
# ClientThread class
################################################################################

class ClientThread(Thread):

  MSG_AUTH = '0'
  MSG_TEXT = '1'

  AUTH_OKAY = 'OKAY'
  AUTH_FAILED = 'FAILED'
  AUTH_NONE = 'NONE'

  def __init__(self,srv,conn,addr,ipc):

    """cretae a new thread that handles client connections"""

    super(ClientThread,self).__init__()
    self.daemon = True
    self.authed = (srv.password is None)

    self.server = srv
    self.socket = conn
    self.address = addr
    self.ipc = ipc

    self.log = srv.log
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
      (typ,msg) = self.get_msg()
      if typ==ClientThread.MSG_AUTH:
        self.do_auth(msg)
        msg = None
      elif typ==ClientThread.MSG_TEXT or typ is None:
        if not self.authed:
          self.log.warning('Remote %s:%s did not attempt Auth' % self.address)
          self.send_msg(ClientThread.AUTH_FAILED,ClientThread.MSG_AUTH)
          raise RuntimeError
        msgs.append(msg)
      else:
        self.log.error('Unsupported msg type "%s"' % typ)
        self.send_msg('Unsupported msg type "%s"; closing connection' % typ)
        raise RuntimeError

    return msgs

  def get_msg(self):

    msg = self.buffer
    while ' ' not in msg:
      s = self.socket.recv(4096)
      if not s:
        self.log.debug('Received EOS from %s:%s' % self.address)
        raise RuntimeError
      msg += s

    length_str = msg.split(' ')[0]
    target = len(length_str)+1+int(length_str)
    while len(msg)<target:
      msg += self.socket.recv(min(target-len(msg),4096))

    (msg,self.buffer) = (msg[:target],msg[target:])
    msg = msg[msg.find(' ')+1:]
    return (msg[0],msg[2:])

  def do_auth(self,msg):

    if self.authed:
      self.send_msg(ClientThread.AUTH_NONE,ClientThread.MSG_AUTH)
      return

    if self.server.password==msg:
      self.authed = True
      self.send_msg(ClientThread.AUTH_OKAY,ClientThread.MSG_AUTH)
      self.log.debug('Successful auth from %s:%s' % self.address)
    else:
      self.send_msg(ClientThread.AUTH_FAILED,ClientThread.MSG_AUTH)
      self.log.warning('Invalid password from %s:%s' % self.address)
      raise RuntimeError

  def send_msg(self,msg,typ=None):

    typ = typ or ClientThread.MSG_TEXT
    msg = typ+' '+msg
    length_str = str(len(msg))
    msg = (length_str+' '+msg)
    target = len(msg)

    sent = 0
    while sent<target:
      sent += self.socket.send(msg[sent:])

################################################################################
# User sub-class
################################################################################

class Client(User):

  def parse(self,info):
    self.address = info
    self.user = '%s:%s@socket' % info

  def get_name(self):
    return self.user

  def get_room(self):
    return None

  def get_base(self):
    return self.user

  def __eq__(self,other):
    if not isinstance(other,Client):
      return False
    return self.address==other.address

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

    hostname = '0.0.0.0' if self.opt('socket.internet') else 'localhost'
    port = self.opt('socket.port')
    pword = self.opt('socket.key_password')

    context = None
    (key,crt) = (self.opt('socket.privkey'),self.opt('socket.pubkey'))
    if key or crt:
      if not (key and crt):
        missing = [x for (x,y) in {'pubkey':crt,'privkey':key}.items() if not y]
        self.log.error('Missing %s; not using SSL' % missing[0])
      else:
        import ssl
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.verify_mode = ssl.CERT_NONE
        try:
          context.load_cert_chain(certfile=crt,keyfile=key,password=pword)
        except Exception as e:
          self.log.debug('Error loading cert chain (%s)' % e.__class__.__name__)
          self.log.error('Invalid privkey password; not using SSL')
          context = None

    self.thread = ServerThread(self.log,
        self.queue,self.event_data,self.event_close,
        self.opt('socket.password'),context)

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

  def process(self):

    if not self.event_data.is_set():
      return

    (address,text) = self.queue.get()
    usr = Client(self,address)

    if self.special_cmds(text):
      return

    msg = Message(usr,text)
    self.bot._cb_message(msg)

    if self.queue.empty():
      self.event_data.clear()

  def shutdown(self):
    if hasattr(self,'event_close'):
      self.event_close.set()
    if self.thread:
      self.thread.join()

  def send(self,text,to):
    self.thread.send(text,to.address)

  def broadcast(self,text,room,frm=None,users=None):
    pass

  def join_room(self,room):
    self.bot._cb_join_room_failure(room,'not supported')

  def part_room(self,room):
    pass

  def _get_rooms(self,flag):
    return []

  def get_occupants(self,room):
    return []

  def get_nick(self,room):
    return 'sibyl'

  def get_real(self,room,nick):
    return nick

  def get_user(self):
    return Client(self,(0,'sibyl'))

  def new_user(self,user,typ=None,real=None):
    return Client(self,(0,user),typ,real)

  def new_room(self,name,nick=None,pword=None):
    return FakeRoom(self,name,nick,pword)

################################################################################

  def get_pass(self):
    """get the cert password or raise an error"""

    return self.opt('socket.key_password') or ''

  def special_cmds(self,text):
    """process special admin commands"""

    if not text.startswith('/'):
      return
    args = text[1:].split(' ')
