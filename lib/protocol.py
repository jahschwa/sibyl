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
#
# If you are implementing a new Protocol you must override the @abstractmethod
# methods in both the User class and the Protocol class
#
# For Messages, you are required to at least use OFFLINE and AVAILABLE;
# all other status types are optional and protocol-dependant
#
# Some functions in Protocol are required to call methods from SibylBot and
# these are noted with "@call" in general this should be the method's last line
#
################################################################################

from abc import ABCMeta,abstractmethod
import os,sys,inspect

################################################################################
# Custom exceptions
################################################################################

class ProtocolError(Exception):
  pass

class PingTimeout(ProtocolError):
  pass

class ConnectFailure(ProtocolError):
  pass

class AuthFailure(ProtocolError):
  pass

class ServerShutdown(ProtocolError):
  pass

################################################################################
# User abstract class
################################################################################

class User(object):
  __metaclass__ = ABCMeta

  # called on object init; the following are already created by __init__:
  #   self.protocol = (Protocol) name of this User's protocol as a str
  #   self.typ = (int) either Message.PRIVATE or Message.GROUP
  #   self.real = (User) the "real" User behind this user (defaults to self)
  # @param user (object) a full username
  @abstractmethod
  def parse(self,user):
    pass

  # @return (str) the username in private chat or the nick name in a room
  @abstractmethod
  def get_name(self):
    pass

  # @return (str) the username without resource identifier
  @abstractmethod
  def get_base(self):
    pass

  # @param other (object) you must check for class equivalence
  # @return (bool) True if self==other (including resource)
  @abstractmethod
  def __eq__(self,other):
    pass

  # @return (str) the full username
  @abstractmethod
  def __str__(self):
    pass

  def __repr__(self):
    return '<%s %s>' % (self.__class__.__name__,str(self))

  # @param proto (Protocol) the associated protocol
  # @param user (object) a user id to parse
  # @param typ (int) [Message.PRIVATE] either Message.GROUP or Message.PRIVATE
  # @param real (User) [self] the "real" user behind this user
  def __init__(self,proto,user,typ=None,real=None):
    self.protocol = proto
    self.typ = (Message.PRIVATE if typ is None else typ)
    self.real = (real or self)
    self.parse(user)

  # @return (int) the type of this User (Message class type enum)
  def get_type(self):
    """return the typ of the User"""
    return self.typ

  # @return (User subclass) the "real" username of this User or None
  def get_real(self):
    """get the "real" User of this User"""
    return self.real

  # set the "real" User info for this User
  # @param real (User) the "real" username of this User
  def set_real(self,real):
    """set the "real" User of this User"""
    self.real = real

  # @return (Protocol) the protocol associated with this User
  def get_protocol(self):
    """return the name of the protocol associated with this User"""
    return self.protocol

  # @param (object) an object to check for base match (no resource)
  # @return (bool) True if other is User and matching protocol and get_base()
  def base_match(self,other):
    if not isinstance(other,User):
      return False
    if self.protocol!=other.protocol:
      return False
    return self.get_base()==other.get_base()

  # override the != operator (you don't have to do this in the subclass)
  # @param other (object)
  # @return (bool) whether self!=other
  def __ne__(self,other):
    return not self==other

  # override hashing to allow as dict keys
  def __hash__(self):
    return hash(self.__str__())

  # don't pickle the protocol; sibylbot will fix it in its persistence code
  def __getstate__(self):
    odict = self.__dict__.copy()
    odict['protocol'] = self.protocol.get_name()
    return odict

################################################################################
# Room class
################################################################################

class Room(object):
  __metaclass__ = ABCMeta

  # get_room flags
  FLAG_CONF = 0
  FLAG_RUNTIME = 1

  FLAG_PARTED = 2
  FLAG_PENDING = 3
  FLAG_IN = 4

  FLAG_ACTIVE = 5
  FLAG_OUT = 6
  FLAG_ALL = 7

  # called on object init; the following are already created by __init__:
  #   self.protocol = name of this Room's protocol as a str
  #   self.nick = the nick name to use in the room (defaults to None)
  #   self.pword = the password for this room (defaults to None)
  # @param name (object) a full roomid
  @abstractmethod
  def parse(self,name):
    pass

  # the return value must be the same for equal Rooms and unique for different
  # @return (str) the name of this Room
  @abstractmethod
  def get_name(self):
    pass

  # @param other (object) you must check for class equivalence
  # @return (bool) true if other is the same room (ignore nick/pword if present)
  @abstractmethod
  def __eq__(self,other):
    pass

  # @param proto (Protocol) the associated protocol
  # @param name (object) the identifier for this Room
  # @param nick (str) [None] the nick name to use in this Room
  # @param pword (str) [None] the password for joining this Room
  def __init__(self,proto,name,nick=None,pword=None):
    self.protocol = proto
    self.nick = nick
    self.pword = pword
    self.parse(name)

  # @return (Protocol) the protocol associated with this Room
  def get_protocol(self):
    """return the name of the protocol associated with this Room"""
    return self.protocol

  # @return (str,None) the nick name to use in this Room
  def get_nick(self):
    """return the nick to use in this Room or None"""
    return self.nick

  # @return (str,None) the password to use when joining this Room
  def get_password(self):
    """return this Room's password or None"""
    return self.pword

  # @return (list of User) the Users in this room
  def get_occupants(self):
    """return the users in this room"""
    return self.protocol.get_occupants(self)

  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  def get_real(self,nick):
    """return the specified nick name's real user"""
    return self.protocol.get_real(self,nick)

  # @return (str) the string version of this Room (includes protocol)
  def __str__(self):
    return self.protocol.get_name()+':'+self.get_name()

  # @return (str) the string object representation of tihs Room (inc proto)
  def __repr__(self):
    return '<Room %s>' % self

  # @param other (object) another object for comparison
  # @return (bool) true if other is not a Room, or has different protocol/name
  def __ne__(self,other):
    return not self==other

  # override hashing to allow as dict keys
  # @return (str) a hash of this Room (depends on protocol and name)
  def __hash__(self):
    return hash(str(self))

  # don't pickle the protocol; sibylbot will fix it in its persistence code
  def __getstate__(self):
    odict = self.__dict__.copy()
    odict['protocol'] = self.protocol.get_name()
    return odict

################################################################################
# Message class
################################################################################

class Message(object):

  # Type enums
  STATUS = 0
  PRIVATE = 1
  GROUP = 2
  ERROR = 3

  # Status enums
  UNKNOWN = -1
  OFFLINE = 0
  EXT_AWAY = 1
  AWAY = 2
  DND = 3
  AVAILABLE = 4

  # Type names
  TYPES = ['STATUS','PRIVATE','GROUP','ERROR']
  STATUSES = ['OFFLINE','EXT_AWAY','AWAY','DND','AVAILABLE']

  # create a new message object with given info
  # @param user (User) the User who sent the Message
  # @param txt (str,unicode) the body of the msg
  # @param typ (int) [Message.PRIVATE] a Message type enum
  # @param status (int) [None] status enum
  # @param msg (str) [None] custom status msg (e.g. "Doing awesome!")
  # @param room (Room) [None] the room that sent the message
  # @param emote (bool) [False] if this is an "emote" message
  #
  #   ===== following used internally by Sibyl=====
  # @param to (User,Room) [None] the destination for this Message
  # @param broadcast (bool) [False] highlight all users (only works for Rooms)
  # @param users (list of User) [[]] additional users to highlight (broadcast)
  # @param hook (bool) [True] execute @botsend hooks for this message
  def __init__(self,user,txt,typ=None,status=None,msg=None,room=None,
      to=None,broadcast=False,users=None,hook=True,emote=False):
    """create a new Message"""

    self.protocol = user.get_protocol() if to is None else to.get_protocol()

    self.typ = (Message.PRIVATE if typ is None else typ)
    if self.typ not in range(0,4):
      raise ValueError('Valid types: Message.STATUS, PRIVATE, GROUP, ERROR')

    if (status is not None) and (status not in range(-1,5)):
      raise ValueError('Valid status: Message.UNKNOWN, OFFLINE, EXT_AWAY, '
          + 'AWAY, DND, AVAILABLE')
    self.status = status

    self.set_text(txt)
    self.user = user
    self.msg = msg
    self.room = room

    self.to = to
    self.broadcast = broadcast
    self.users = users or []
    self.hook = hook
    self.emote = emote

  # @return (User,Room) the sender of this Message usable for a reply
  def get_from(self):
    """return the sender of this Message"""
    return (self.room or self.user)

  # @return (User) the User who sent this Message
  def get_user(self):
    """return the User who sent this Message"""
    return self.user

  # @return (Room,None) the Room that sent this Message
  def get_room(self):
    """return the Room that sent this Message"""
    return self.room

  # @return (str,unicode) the body of this Message
  def get_text(self):
    """return the body of the message"""
    return self.txt

  # @param text (str,unicode) the body of this Message to set
  def set_text(self,text):
    """set the body of the message"""

    if isinstance(text,str):
      text = text.decode('utf8')
    elif not isinstance(text,unicode):
      text = unicode(text)
    self.txt = text

  # @return (int) the type of this Message (Message class type enum)
  def get_type(self):
    """return the typ of the message"""
    return self.typ

  # @return (tuple of (int,str)) the Message status enum and status msg
  def get_status(self):
    """return the status e.g. (Message.OFFLINE,'Be back later :]')"""
    return (self.status,self.msg)

  # @return (Protocol) the protocol associated with this Message
  def get_protocol(self):
    """return the name of the protocol associated with this Message"""
    return self.protocol

  # @return (User,Room) the destination for this Message
  def get_to(self):
    """return the destination User or Room for this Message"""
    return self.to

  # @return (bool) whether this Message should be broadcast
  def get_broadcast(self):
    """return True/False for broadcasting this Message"""
    return self.broadcast

  # @return (list of User) additional users to highlight (broadcast)
  def get_users(self):
    """return additional users to highlight when broadcasting"""
    return self.users

  # @return (bool) whether to run @botsend hooks for this Message
  def get_hook(self):
    """return whether to run @botsend hooks for this Message"""
    return self.hook

  # @return (bool) whether this Message is an "emote" message
  def get_emote(self):
    """return whether this Message was sent as an "emote" message"""
    return self.emote

  # @param typ (int) Message type enum
  # @return (str) human-readable Message type
  @staticmethod
  def type_to_str(typ):
    """return a human-readable Message type given a Message type enum"""
    if typ not in range(0,len(Message.TYPES)):
      raise ValueError('Invalid Message type')
    return Message.TYPES[typ]

  # don't pickle the protocol; sibylbot will fix it in its persistence code
  def __getstate__(self):
    odict = self.__dict__.copy()
    odict['protocol'] = self.protocol.get_name()
    return odict

################################################################################
# Protocol abstract class
################################################################################

class Protocol(object):
  __metaclass__ = ABCMeta

  # called on bot init; the following are guaranteed to exist:
  #   self.bot = SibylBot instance
  #   self.log = the logger you should use
  @abstractmethod
  def setup(self):
    pass

  # @raise (ConnectFailure) if can't connect to server
  # @raise (AuthFailure) if failed to authenticate to server
  @abstractmethod
  def connect(self):
    pass

  # @return (bool) True if we are connected to the server
  @abstractmethod
  def is_connected(self):
    pass

  # receive/process messages and call bot._cb_message()
  # must ignore msgs from myself and from users not in any of our rooms
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @raise (PingTimeout) if implemented
  # @raise (ConnectFailure) if disconnected
  # @raise (ServerShutdown) if server shutdown
  @abstractmethod
  def process(self):
    pass

  # called when the bot is exiting for whatever reason
  @abstractmethod
  def shutdown(self):
    pass

  # send a message to a user
  # @param mess (Message) message to be sent
  # @raise (ConnectFailure) if failed to send message
  # Check: get_emote()
  @abstractmethod
  def send(self,mess):
    pass

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param mess (Message) the message to broadcast
  # @return (str,unicode) the text that was actually sent
  # Check: get_user(), get_users()
  @abstractmethod
  def broadcast(self,mess):
    pass

  # join the specified room using the specified nick and password
  # @param room (Room) the room to join
  # @call bot._cb_join_room_success(room) on successful join
  # @call bot._cb_join_room_failure(room,error) on failed join
  @abstractmethod
  def join_room(self,room):
    pass

  # part the specified room
  # @param room (Room) the room to leave
  @abstractmethod
  def part_room(self,room):
    pass

  # helper function for get_rooms() for protocol-specific flags
  # only needs to handle: FLAG_PARTED, FLAG_PENDING, FLAG_IN, FLAG_ALL
  # @param flag (int) one of Room.FLAG_* enums
  # @return (list of Room) rooms matching the flag
  @abstractmethod
  def _get_rooms(self,flag):
    pass

  # @param room (Room) the room to query
  # @return (list of User) the Users in the specified room
  @abstractmethod
  def get_occupants(self,room):
    pass

  # @param room (Room) the room to query
  # @return (str) the nick name we are using in the specified room
  @abstractmethod
  def get_nick(self,room):
    pass

  # @param room (Room) the room to query
  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  @abstractmethod
  def get_real(self,room,nick):
    pass

  # @return (User) our username
  @abstractmethod
  def get_user(self):
    pass

  # @param user (str) a user id to parse
  # @param typ (int) [Message.PRIVATE] either Message.GROUP or Message.PRIVATE
  # @param real (User) [self] the "real" user behind this user
  # @return (User) a new instance of this protocol's User subclass
  @abstractmethod
  def new_user(self,user,typ=None,real=None):
    pass

  # @param name (object) the identifier for this Room
  # @param nick (str) [None] the nick name to use in this Room
  # @param pword (str) [None] the password for joining this Room
  # @return (Room) a new instance of this protocol's Room subclass
  @abstractmethod
  def new_room(self,name,nick=None,pword=None):
    pass

  # @param bot (SibylBot) the sibyl instance
  # @param log (Logger) the logger this protocol should use
  def __init__(self,bot,log):

    self.bot = bot
    self.log = log
    self.setup()

  # @param other (object) another object for comparison
  # @return (bool) if other is a Protocol and has the same name
  def __eq__(self,other):
    if not isinstance(other,Protocol):
      return False
    return self.get_name()==other.get_name()

  # override the != operator (you don't have to do this in the subclass)
  # @param other (object)
  # @return (bool) whether self!=other
  def __ne__(self,other):
    return not self==other

  # override hash for use as dict keys
  def __hash__(self):
    return hash(self.get_name())

  # @param opt (str) name of the option to get
  # @return (object) the value of the option
  def opt(self,opt):
    return self.bot.opt(opt)

  # @return (str) the name of the protocol based on filename
  def get_name(self):
    return self.__module__.split('_')[1]

  # @param room (Room) the room to check
  # @return (bool) whether we are currently connected and in the room
  def in_room(self,room):
    return room in self.get_rooms()

  # @param flags (int, list of int) Room.FLAG_* enum(s)
  # @return (list of Room) the Rooms matching all given flags (i.e. AND)
  def get_rooms(self,flags=None):
    """return our rooms, optionally only those we are in"""

    if flags is None:
      flags = [Room.FLAG_IN]
    elif not isinstance(flags,list):
      flags = [flags]
    rooms = set(self._get_rooms(Room.FLAG_ALL))

    for flag in flags:

      if flag in (Room.FLAG_CONF,Room.FLAG_RUNTIME):
        pname = self.get_name()
        conf = [Room(room['room'],proto=pname) for room in
          self.opt('rooms').get(pname,[])]
        if flag==Room.FLAG_CONF:
          rooms.intersection_update(conf)
        elif flag==Room.FLAG_RUNTIME:
          rooms.difference_update(conf)

      elif flag==Room.FLAG_ACTIVE:
        self.__add_rooms(rooms,[Room.FLAG_IN,Room.FLAG_PENDING])
      elif flag==Room.FLAG_OUT:
        self.__add_rooms(rooms,[Room.FLAG_PARTED,Room.FLAG_PENDING])
      else:
        rooms.intersection_update(self._get_rooms(flag))

    return list(rooms)

  # @param rooms (set) set to add rooms to
  # @param flags (list of int) list of Room.FLAG_* enums
  def __add_rooms(self,rooms,flags):
    """helper function for get_rooms"""

    temp = set()
    for flag in flags:
      temp.update(self._get_rooms(flag))
    rooms.intersection_update(temp)
