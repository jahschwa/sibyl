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

from sibyl.lib.protocol import User,Room,Message,Protocol
from sibyl.lib.protocol import PingTimeout,ConnectFailure,AuthFailure,ServerShutdown

from sibyl.lib.decorators import botconf

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError, MatrixHttpApi
import matrix_client.user as mxUser
import matrix_client.room as mxRoom

################################################################################
# Config options
################################################################################

@botconf
def conf(bot):
  return [
    {"name": "username", "req": True},
    {"name": "password", "req": True},
    {"name": "server", "req": True}
  ]

################################################################################
# User sub-class
################################################################################

class MatrixUser(User):

  # called on User init; the following are already created by __init__:
  #   self.protocol = name of this User's protocol as a str
  #   self.real = the "real" User behind this user (defaults to self)
  # @param user (str) username to parse
  # @param typ (int) is either Message.PRIVATE or Message.GROUP
  def parse(self,user,typ):
    if(isinstance(user,mxUser)):
      self.user = user
    elif(isinstance(user,basestring)):
      self.user = client.get_user(user)
    else:
      raise TypeError("User parameter to parse must be a string")

  # @return (str) the username in private chat or the nick name in a room
  def get_name(self):
    return self.user.get_display_name()

  # @return (Room) the room this User is a member of or None
  def get_room(self):
    return self.room

  # @return (str) the username without resource identifier
  def get_base(self):
    return self.user.user_id

  # @param other (object) you must check for class equivalence
  # @return (bool) True if self==other (including resource)
  def __eq__(self,other):
    if(not isinstance(other,MatrixUser)):
      return False
    return(self.get_base() == other.get_base())

  # @return (str) the full username
  def __str__(self):
    return self.get_base()

  def __init__(self,client,user,typ,roomid=None,real=None,proto=None):
    super(MatrixUser,self).__init__(user,typ,real,proto)
    self.client = client
    self.room = MatrixRoom(roomid)

################################################################################
# Room sub-class
################################################################################

class MatrixRoom(Room):

  def __init__(self,client,name,proto=None):

    super(MatrixRoom,self).__init__()

    self.room = mxRoom(client,name) # Assumes a room ID for now

    # Jon: if name is an alias resolve it to an id and store it

################################################################################
# Protocol sub-class
################################################################################

class MatrixProtocol(Protocol):

  # called on bot init; the following are already created by __init__:
  #   self.bot = SibylBot instance
  #   self.log = the logger you should use
  def setup(self):
    self.connected = False
    self.rooms = {}
    bot.add_var("credentials",persist=True)

  # @raise (ConnectFailure) if can't connect to server
  # @raise (AuthFailure) if failed to authenticate to server
  def connect(self):
    homeserver = self.opt('matrix.server')
    user = self.opt('matrix.username')
    pw = self.opt('matrix.password')

    self.log.debug("Connecting to %s" % homeserver)

    try:
      self.log.debug("Logging in as %s" % user)
      
      # Log in with the existing access token if we already have a token
      if(bot.credentials and bot.credentials[0] == user):
        self.client = MatrixClient(homeserver, token=bot.credentials[1])
      # Otherwise, log in with the configured username and password
      else:
        token = self.client.login_with_password(user,pw)
        bot.credentials = (user, token)
        
      self.rooms = self.client.get_rooms()
      self.log.debug("Already in rooms: %s" % self.rooms)
    except MatrixRequestError:
      self.log.debug("Failed to connect to homeserver!")
      raise ConnectFailure

  # @return (bool) True if we are connected to the server
  def is_connected(self):
    raise NotImplementedError

  # called whenever the bot detects a disconnect as insurance
  def disconnected(self):
    raise NotImplementedError

  # receive/process messages and call bot._cb_message()
  # must ignore msgs from myself and from users not in any of our rooms
  # @param wait (int) time to wait for new messages before returning
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @raise (PingTimeout) if implemented
  # @raise (ConnectFailure) if disconnected
  # @raise (ServerShutdown) if server shutdown
  def process(self,wait=0):
    raise NotImplementedError

  # called when the bot is exiting for whatever reason
  # NOTE: sibylbot will already call part_room() on every room in get_rooms()
  def shutdown(self):
    raise NotImplementedError

  # send a message to a user
  # @param text (str,unicode) text to send
  # @param to (User,Room) recipient
  def send(self,text,to):
    raise NotImplementedError

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param text (str,unicode) body of the message
  # @param room (Room) room to broadcast in
  # @param frm (User) [None] the User requesting the broadcast
  def broadcast(self,text,room,frm=None):
    raise NotImplementedError

  # join the specified room using the specified nick and password
  # @param room (Room) the room to join
  # @call bot._cb_join_room_success(room) on successful join
  # @call bot._cb_join_room_failure(room,error) on failed join
  def join_room(self,room):
    raise NotImplementedError

  # part the specified room
  # @param room (Room) the room to leave
  def part_room(self,room):
    raise NotImplementedError

  # helper function for get_rooms() for protocol-specific flags
  # only needs to handle: FLAG_PARTED, FLAG_PENDING, FLAG_IN, FLAG_ALL
  # @param flag (int) one of Room.FLAG_* enums
  # @return (list of Room) rooms matching the flag
  def _get_rooms(self,flag):
    raise NotImplementedError

  # @param room (Room) the room to query
  # @return (list of User) the Users in the specified room
  def get_occupants(self,room):
    raise NotImplementedError

  # @param room (Room) the room to query
  # @return (str) the nick name we are using in the specified room
  def get_nick(self,room):
    raise NotImplementedError

  # @param room (Room) the room to query
  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  def get_real(self,room,nick):
    raise NotImplementedError

  # @return (User) our username
  def get_username(self):
    raise NotImplementedError

  def new_user(self,user,typ,real=None):
    return MatrixUser(self.client,user,typ,real,proto='matrix')

  def new_room(self,room_id_or_alias):
    raise NotImplementedError

################################################################################
# Helper functions
################################################################################
