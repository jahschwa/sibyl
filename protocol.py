#!/usr/bin/env python
#
# User, Message, and Protocol classes for use with Sibyl
# If you are implementing a new Protocol you must override every method in both
# the User class and the Protocol class

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
# User class                                                                   #
################################################################################

class User(object):
  __metaclass__ = ABCMeta

  @abstractmethod
  def parse(self,user,typ):
    pass

  @abstractmethod
  def get_room(self):
    pass

  @abstractmethod
  def get_base(self):
    pass

  @abstractmethod
  def __eq__(self,other):
    pass

  @abstractmethod
  def __str__(self):
    pass

  def __init__(self,user,typ=None):

    self.domain = None
    self.user = None
    self.resource = None

    self.conference = None
    self.room = None
    self.nick = None
    self.real = None
    
    self.parse(user,typ)

  def get_nick(self):
    return self.nick

  def get_domain(self):
    return self.domain

  def get_conference(self):
    return self.conference

  def get_user(self):
    return self.user

  def get_resource(self):
    return self.resource

  def get_real(self):
    return self.real

  def set_real(self,user):
    self.real = user
    

################################################################################
# Message class                                                                #
################################################################################

class Message(object):

  STATUS = 0
  PRIVATE = 1
  GROUP = 2
  ERROR = 3

  TYPES = ['STATUS','PRIVATE','GROUP','ERROR']

  def __init__(self,typ,frm,txt,show=None,status=None):
    """create a new Message"""

    if typ not in range(0,4):
      raise ValueError('Valid types: Message.STATUS, PRIVATE, GROUP, ERROR')
    self.typ = typ
    
    self.frm = frm
    self.txt = txt
    self.show = show
    self.status = status

  def get_from(self):
    """return the username of the sender"""

    return self.frm

  def get_text(self):
    """return the body of the message"""

    return self.txt

  def set_text(self,text):
    """set the body of the message"""

    self.txt = text

  def get_type(self):
    """return the typ of the message"""

    return self.typ

  def get_show(self):
    """return the show state (e.g. available, dnd)"""

    return self.show

  def get_status(self):
    """return the status text"""

    return self.status

  @staticmethod
  def type_to_str(typ):
    """return a human-readable type"""

    if typ not in range(0,4):
      return 'INVALID'
    return Message.TYPES[typ]

################################################################################
# Protocol abstract class                                                      #
################################################################################

class Protocol(object):
  __metaclass__ = ABCMeta

  @abstractmethod
  def __init__(self,callback):
    """create a new object that calls "callback" upon receiving a msg"""

    pass

  @abstractmethod
  def get_name(self):
    """return the name of this protocol (e.g. 'XMPP')"""

    pass

  @abstractmethod
  def connect(self,user,pword):
    """connect and authenticate to the server"""

    pass

  @abstractmethod
  def is_connected(self):
    """return True/False if we are connected"""

    pass

  @abstractmethod
  def disconnect(self):
    """disconnect from the server"""

    pass

  @abstractmethod
  def process(self):
    """process messages and call callback as needed"""

    pass

  @abstractmethod
  def send(self,text,user):
    """send a message with given text to given user"""

    pass

  @abstractmethod
  def join_room(self,room,nick,pword=None):
    """join a room and return True if joined successfully or False otherwise"""

    pass

  @abstractmethod
  def part_room(self,room):
    """leave the specified room"""

    pass

  @abstractmethod
  def in_room(self,room):
    """return True/False if we are in the given room"""

    pass

  @abstractmethod
  def get_rooms(self,in_only=False):
    """return all our rooms, or just the ones we are in"""

    pass

  @abstractmethod
  def get_nick(self,room):
    """return our nick in the specified room"""

    pass
