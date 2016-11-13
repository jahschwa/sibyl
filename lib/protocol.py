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
  def __init__(self):
    filename = os.path.basename(inspect.stack()[1][1])
    self.protocol = filename.split(os.path.extsep)[0].split('_')[1]

class PingTimeout(ProtocolError):
  pass

class ConnectFailure(ProtocolError):
  pass

class AuthFailure(ProtocolError):
  pass

class ServerShutdown(ProtocolError):
  pass

################################################################################
# Protocol auto-completion super class
################################################################################

class ProtocolAware(object):

  def __init__(self,proto):

    if not proto:

      filepath = os.path.abspath(inspect.stack()[2][1])
      dirname = os.path.dirname(filepath).split(os.path.sep)[-1]
      proto = os.path.basename(filepath).split(os.path.extsep)[0]

      if 'sibyl_' in proto and dirname=='protocols':
        proto = proto.split('_')[-1]
      else:
        raise ValueError('You can only omit param "proto" in a Protocol subclass')

    self.protocol = proto

################################################################################
# User abstract class
################################################################################

class User(ProtocolAware):
  __metaclass__ = ABCMeta

  # called on bot init; the following are already created by __init__:
  #   self.protocol = name of this User's protocol as a str
  #   self.real = the "real" User behind this user (defaults to self)
  # @param user (object) a full username
  # @param typ (int) is either Message.PRIVATE or Message.GROUP
  @abstractmethod
  def parse(self,user,typ):
    pass

  # @return (str) the username in private chat or the nick name in a room
  @abstractmethod
  def get_name(self):
    pass

  # @return (Room) the room this User is a member of or None
  @abstractmethod
  def get_room(self):
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

  # @param user (object) a user id to parse
  # @param typ (int) either Message.GROUP or Message.PRIVATE
  # @param real (User) [self] the "real" user behind this user
  # @param proto (str) [auto-gen] name of the associated protocol
  def __init__(self,user,typ,real=None,proto=None):

    super(User,self).__init__(proto)

    self.real = real
    self.parse(user,typ)

  # @return (User subclass) the "real" username of this User or None
  def get_real(self):
    """get the "real" User of this User"""
    return self.real

  # set the "real" User info for this User
  # @param real (User) the "real" username of this User
  def set_real(self,real):
    """set the "real" User of this User"""
    self.real = real

  # @return (str) the protocol associated with this User
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

################################################################################
# Room class                                                                   #
################################################################################

class Room(ProtocolAware):

  # get_room flags
  FLAG_CONF = 0
  FLAG_RUNTIME = 1

  FLAG_PARTED = 2
  FLAG_PENDING = 3
  FLAG_IN = 4

  FLAG_ACTIVE = 5
  FLAG_OUT = 6
  FLAG_ALL = 7

  # @param name (str) the identifier for this Room
  # @param nick (str) [None] the nick name to use in this Room
  # @param pword (str) [None] the password for joining this Room
  # @param proto (str) [auto-gen] name of the associated protocol
  def __init__(self,name,nick=None,pword=None,proto=None):

    super(Room,self).__init__(proto)

    self.name = name
    self.nick = nick
    self.pword = pword

  # @return (str) the protocol associated with this Room
  def get_protocol(self):
    """return the name of the protocol associated with this Room"""
    return self.protocol

  # @return (str) the name of this Room
  def get_name(self):
    """return the string representation of this Room"""
    return self.name

  # @return (str,None) the nick name to use in this Room
  def get_nick(self):
    """return the nick to use in this Room or None"""
    return self.nick

  # @return (str,None) the password to use when joining this Room
  def get_password(self):
    """return this Room's password or None"""
    return self.pword

  # @return (str) the string version of this Room (includes protocol)
  def __str__(self):
    return self.protocol+':'+self.name

  # @return (str) the string object representation of tihs Room (inc proto)
  def __repr__(self):
    return '<Room %s:%s>' % (self.protocol,self.name)

  # @param other (object) another object for comparison
  # @return (bool) true if other is a Room, and has same protocol and name
  def __eq__(self,other):
    if not isinstance(other,Room):
      return False
    return self.name==other.name and self.protocol==other.protocol

  # @param other (object) another object for comparison
  # @return (bool) true if other is not a Room, or has different protocol/name
  def __ne__(self,other):
    return not self==other

  # override hashing to allow as dict keys
  # @return (str) a hash of this Room (depends on protocol and name)
  def __hash__(self):
    return hash(str(self))

################################################################################
# Message class                                                                #
################################################################################

class Message(ProtocolAware):

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
  # @param typ (int) a Message type enum
  # @param frm (User) the User who sent the Message
  # @param txt (str,unicode) the body of the msg
  # @param status (str) [None] status enum
  # @param msg (str) [None] custom status msg (e.g. "Doing awesome!")
  # @param proto (str) [auto-gen] name of the associated protocol
  def __init__(self,typ,frm,txt,status=None,msg=None,proto=None):
    """create a new Message"""

    super(Message,self).__init__(proto)

    if typ not in range(0,4):
      raise ValueError('Valid types: Message.STATUS, PRIVATE, GROUP, ERROR')
    self.typ = typ

    if (status is not None) and (status not in range(-1,5)):
      raise ValueError('Valid status: Message.UNKNOWN, OFFLINE, EXT_AWAY, '+
          'AWAY, DND, AVAILABLE')
    self.status = status

    self.frm = frm
    self.txt = txt
    self.msg = msg

  # @return (User) the User who sent this Message
  def get_from(self):
    """return the User who sent this messge"""
    return self.frm

  # @return (str,unicode) the body of this Message
  def get_text(self):
    """return the body of the message"""
    return self.txt

  # @param text (str,unicode) the body of this Message to set
  def set_text(self,text):
    """set the body of the message"""
    self.txt = text

  # @return (int) the type of this Message (Message class type enum)
  def get_type(self):
    """return the typ of the message"""
    return self.typ

  # @return (tuple of (int,str)) the Message status enum and status msg
  def get_status(self):
    """return the status e.g. (Message.OFFLINE,'Be back later :]')"""
    return (self.status,self.msg)

  # @return (str) the protocol associated with this Message
  def get_protocol(self):
    """return the name of the protocol associated with this Message"""
    return self.protocol

  # @param typ (int) Message type enum
  # @return (str) human-readable Message type
  @staticmethod
  def type_to_str(typ):
    """return a human-readable Message type given a Message type enum"""
    if typ not in range(0,len(Message.TYPES)):
      raise ValueError('Invalid Message type')
    return Message.TYPES[typ]

################################################################################
# Protocol abstract class                                                      #
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

  # called whenever the bot detects a disconnect as insurance
  @abstractmethod
  def disconnected(self):
    pass

  # receive/process messages and call bot._cb_message()
  # must ignore msgs from myself and from users not in any of our rooms
  # @param wait (int) time to wait for new messages before returning
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @raise (PingTimeout) if implemented
  # @raise (ConnectFailure) if disconnected
  # @raise (ServerShutdown) if server shutdown
  @abstractmethod
  def process(self,wait=0):
    pass

  # called when the bot is exiting for whatever reason
  # NOTE: sibylbot will already call part_room() on every room in get_rooms()
  @abstractmethod
  def shutdown(self):
    pass

  # send a message to a user
  # @param text (str,unicode) text to send
  # @param to (User,Room) recipient
  @abstractmethod
  def send(self,text,to):
    pass

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param text (str,unicode) body of the message
  # @param room (Room) room to broadcast in
  # @param frm (User) [None] the User requesting the broadcast
  @abstractmethod
  def broadcast(self,text,room,frm=None):
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
  def get_username(self):
    pass

  # @param bot (SibylBot) the sibyl instance
  # @param log (Logger) the logger this protocol should use
  def __init__(self,bot,log):

    self.bot = bot
    self.log = log
    self.setup()

  # @param opt (str) name of the option to get
  # @return (object) the value of the option
  def opt(self,opt):
    return self.bot.opt(opt)

  # @return (str) the name of the protocol based on filename
  def get_name(self):
    return self.__module__.split('_')[1]

  # @param user (object) a user id to parse
  # @param typ (int) either Message.GROUP or Message.PRIVATE
  # @param real (User) [self] the "real" user behind this user
  def new_user(self,user,typ,real=None):

    return self.get_username().__class__(user,typ,real,proto=self.get_name())

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
