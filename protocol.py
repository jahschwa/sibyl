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

################################################################################
# Custom exceptions                                                            #
################################################################################

class PingTimeout(Exception):
  pass

class ConnectFailure(Exception):
  pass

class AuthFailure(Exception):
  pass

class ServerShutdown(Exception):
  pass

################################################################################
# User abstract class                                                          #
################################################################################

class User(object):
  __metaclass__ = ABCMeta

  # called on object init to guarantee some variables are always initialised
  # @param user (str) a full username
  # @param typ (int) is either Message.PRIVATE or Message.GROUP
  @abstractmethod
  def parse(self,user,typ):
    pass

  # @return (str) the username in private chat or the nick name in a room
  @abstractmethod
  def get_name(self):
    pass

  # @return (str) the room this User is a member of or None
  @abstractmethod
  def get_room(self):
    pass

  # @return (str) the username without resource identifier
  @abstractmethod
  def get_base(self):
    pass

  # @param other (object) you must check for class equivalence
  # @return (bool) True if self==other
  @abstractmethod
  def __eq__(self,other):
    pass

  # @return (str) the full username
  @abstractmethod
  def __str__(self):
    pass

  # initialise the User object and call parse
  def __init__(self,user,typ):
    self.real = None
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

  # override the != operator (you don't have to do this in the subclass)
  # @param other (object)
  # @return (bool) whether self!=other
  def __ne__(self,other):
    return not self==other

################################################################################
# Message class                                                                #
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

  # create a new message object with given info
  # @param typ (int) a Message type enum
  # @param frm (User) the User who sent the Message
  # @param txt (str,unicode) the body of the msg
  # @param status (str) [None] status enum
  # @param msg (str) [None] custom status msg (e.g. "Doing awesome!")
  def __init__(self,typ,frm,txt,status=None,msg=None):
    """create a new Message"""

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
    """return the status (e.g. Message.OFFLINE)"""
    return (self.status,self.msg)

  # @param typ (int) Message type enum
  # @return (str) human-readable Message type
  @staticmethod
  def type_to_str(typ):
    """return a human-readable Message type given a Message type enum"""
    if typ not in range(0,4):
      return 'INVALID'
    return Message.TYPES[typ]

################################################################################
# Protocol abstract class                                                      #
################################################################################

class Protocol(object):
  __metaclass__ = ABCMeta

  # @param bot (SibylBot) the sibyl instance
  # @param log (Logger) the logger this protocol should use
  @abstractmethod
  def __init__(self,bot,log):
    pass

  # connect to the server
  # @param user (str) username for the chat account
  # @param pword (str) password for the chat account
  # @raise (ConnectFailure) if can't connect to server
  # @raise (AuthFailure) if failed to authenticate to server
  @abstractmethod
  def connect(self,user,pword):
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
  # this function should take/block for around 1 second if possible
  # must ignore msgs from myself and from users not in any of our rooms
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @return (Message) the received Message
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
  # @param text (str,unicode) text to send
  # @param to (User) send to a User
  # @param to (str) send to a room
  @abstractmethod
  def send(self,text,to):
    pass

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param text (str,unicode) body of the message
  # @param room (str) room to broadcast in
  # @param frm (User) [None] the User requesting the broadcast
  @abstractmethod
  def broadcast(self,text,room,frm=None):
    pass

  # join the specified room user the specified nick and password
  # @call bot._cb_join_room_success(room) on successful join
  # @call bot._cb_join_room_failure(room,error) on failed join
  # @param room (str) the room to join
  # @param nick (str) the nick name to use in the room
  # @param pword (str) [None] the password for the room
  @abstractmethod
  def join_room(self,room,nick,pword=None):
    pass

  # part the specified room
  # @param room (str) the room to leave
  @abstractmethod
  def part_room(self,room):
    pass

  # @param room (str) the room to check
  # @return (bool) whether we are currently connected and in the room
  @abstractmethod
  def in_room(self,room):
    pass

  # return the rooms we have joined in the past and present
  # @param in_only (bool) [False] only return the rooms we are currently in
  # @return (list of str) our rooms
  @abstractmethod
  def get_rooms(self,in_only=False):
    pass

  # @param room (str) the room to query
  # @return (list of User) the Users in the specified room
  @abstractmethod
  def get_occupants(self,room):
    pass

  # @param room (str) the room to query
  # @return (str) the nick name we are using in the specified room
  @abstractmethod
  def get_nick(self,room):
    pass

  # @param room (str) the room to query
  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  @abstractmethod
  def get_real(self,room,nick):
    pass

  # create a new User using this Protocol's custom User subclass
  # @param user (str) the new username to convert
  # @param typ (int) Message type enum (either PRIVATE or GROUP)
  @abstractmethod
  def new_user(self,user,typ):
    pass
