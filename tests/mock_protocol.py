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

import sys,os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from lib.protocol import Protocol,Message,ConnectFailure
from mock_user import MockUser

class QueueEmpty(Exception):
  pass

class MockProtocol(Protocol):

  def queue_msg(self,msg=None):
    self.log.debug('queue_msg(%s)' % msg)
    if not msg:
      user = MockUser('MOCK_USERNAME',Message.PRIVATE)
      msg = Message(Message.PRIVATE,user,'MOCK_BODY')
    self.queue.insert(0,msg)

  def setup(self):
    self.conn = False
    self.rooms = []
    self.queue = []

  def connect(self,ex=None):
    self.log.debug('connect')
    if ex:
      raise ex
    self.conn = True

  def is_connected(self):
    self.log.debug('is_connected')
    return self.conn

  def disconnected(self):
    self.log.debug('disconnected')
    self.conn = False

  def process(self,msg=None,ex=None):
    self.log.debug('process')
    if ex:
      raise ex
    if not msg:
      if self.queue:
        msg = self.queue.pop()
        if not isinstance(msg,Message):
          raise msg
      else:
        raise QueueEmpty
    self.log.debug('type: %s, message: %s' %
        (Message.type_to_str(msg.get_type()),msg.get_text()))
    self.bot._cb_message(msg)

  def shutdown(self):
    self.log.debug('shutdown')
    pass

  def send(self,text,to):
    self.log.debug('send(%s,%s)' % (text,to))
    pass

  def broadcast(self,text,room,frm=None):
    self.log.debug('broadcast(%s,%s,%s)' % (text,room,frm))
    pass

  def join_room(self,room,nick,pword=None,success=True):
    self.log.debug('join_room(%s,%s,%s)' % (room,nick,pword))
    if not success:
      self.log.debug('join_room failed')
      self.bot._cb_join_room_failure(room,'MOCK_JOIN_ERR')
      return
    self.log.debug('join_room success')
    self.rooms.append(room)
    self.bot._cb_join_room_success(room)

  def part_room(self,room):
    self.log.debug('part_room(%s)' % room)
    del self.rooms[self.rooms.index(room)]

  def in_room(self,room):
    self.log.debug('in_room(%s)' % room)
    return room in self.rooms

  def get_rooms(self,in_only=False):
    self.log.debug('get_rooms')
    return self.rooms

  def get_occupants(self,room):
    self.log.debug('get_occupants(%s)' % room)
    return []

  def get_nick(self,room):
    self.log.debug('get_nick(%s)' % room)
    return 'MOCK_NICKNAME'

  def get_real(self,room,nick):
    self.log.debug('get_real(%s,%s)' % (room,nick))
    return MockUser('MOCK_REALNAME',Message.PRIVATE)

  def new_user(self,user,typ):
    self.log.debug('new_user(%s,%s)' % (user,typ))
    return MockUser('MOCK_NEW_USER')
