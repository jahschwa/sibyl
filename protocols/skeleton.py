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

from lib.protocol import User,Message,Protocol
from lib.protocol import PingTimeout,ConnectFailure,AuthFailure,ServerShutdown

from lib.decorators import botconf

################################################################################
# Config options                                                               #
################################################################################

@botconf
def conf(bot):
  return []

################################################################################
# User sub-class                                                               #
################################################################################

class MYUSER(User):

  # called on object init to guarantee some variables are always initialised
  # @param user (str) a full username
  # @param typ (int) is either Message.PRIVATE or Message.GROUP
  def parse(self,user,typ):
    raise NotImplementedError

  # @return (str) the username in private chat or the nick name in a room
  def get_name(self):
    raise NotImplementedError

  # @return (str) the room this User is a member of or None
  def get_room(self):
    raise NotImplementedError

  # @return (str) the username without resource identifier
  def get_base(self):
    raise NotImplementedError

  # @param other (object) you must check for class equivalence
  # @return (bool) True if self==other
  def __eq__(self,other):
    raise NotImplementedError

  # @return (str) the full username
  def __str__(self):
    raise NotImplementedError

################################################################################
# Protocol sub-class                                                           #
################################################################################

class MYPROTOCOL(Protocol):

  # called on bot init; the following are guaranteed to exist:
  #   self.bot = SibylBot instance
  #   self.log = the logger you should use
  def setup(self):
    raise NotImplementedError

  # @raise (ConnectFailure) if can't connect to server
  # @raise (AuthFailure) if failed to authenticate to server
  def connect(self):
    raise NotImplementedError

  # @return (bool) True if we are connected to the server
  def is_connected(self):
    raise NotImplementedError

  # called whenever the bot detects a disconnect as insurance
  def disconnected(self):
    raise NotImplementedError

  # receive/process messages and call bot._cb_message()
  # this function should take/block for around 1 second if possible
  # must ignore msgs from myself and from users not in any of our rooms
  # @param wait (int) time to wait for new messages before returning
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @return (Message) the received Message
  # @raise (PingTimeout) if implemented
  # @raise (ConnectFailure) if disconnected
  # @raise (ServerShutdown) if server shutdown
  def process(self,wait=0):
    raise NotImplementedError

  # called when the bot is exiting for whatever reason
  def shutdown(self):
    raise NotImplementedError

  # send a message to a user
  # @param text (str,unicode) text to send
  # @param to (User) send to a User
  # @param to (str) send to a room
  def send(self,text,to):
    raise NotImplementedError

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param text (str,unicode) body of the message
  # @param room (str) room to broadcast in
  # @param frm (User) [None] the User requesting the broadcast
  def broadcast(self,text,room,frm=None):
    raise NotImplementedError

  # join the specified room user the specified nick and password
  # @call bot._cb_join_room_success(room) on successful join
  # @call bot._cb_join_room_failure(room,error) on failed join
  # @param room (str) the room to join
  # @param nick (str) the nick name to use in the room
  # @param pword (str) [None] the password for the room
  def join_room(self,room,nick,pword=None):
    raise NotImplementedError

  # part the specified room
  # @param room (str) the room to leave
  def part_room(self,room):
    raise NotImplementedError

  # @param room (str) the room to check
  # @return (bool) whether we are currently connected and in the room
  def in_room(self,room):
    raise NotImplementedError

  # return the rooms we have joined in the past and present
  # @param in_only (bool) [False] only return the rooms we are currently in
  # @return (list of str) our rooms
  def get_rooms(self,in_only=False):
    raise NotImplementedError

  # @param room (str) the room to query
  # @return (list of User) the Users in the specified room
  def get_occupants(self,room):
    raise NotImplementedError

  # @param room (str) the room to query
  # @return (str) the nick name we are using in the specified room
  def get_nick(self,room):
    raise NotImplementedError

  # @param room (str) the room to query
  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  def get_real(self,room,nick):
    raise NotImplementedError

  # @return (User) our username
  def get_username(self):
    raise NotImplementedError

  # create a new User using this Protocol's custom User subclass
  # @param user (str) the new username to convert
  # @param typ (int) Message type enum (either PRIVATE or GROUP)
  def new_user(self,user,typ):
    raise NotImplementedError

################################################################################
# Helper functions                                                             #
################################################################################
