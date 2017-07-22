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

import time,smtplib,imaplib,email
from email.mime.text import MIMEText
from threading import Thread
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
    {'name':'address','req':True},
    {'name':'password','req':True},
    {'name':'delete','default':True,'parse':bot.conf.parse_bool},
    {'name':'imap'},
    {'name':'smtp'},
    {'name':'key','parse':bot.conf.parse_pass}
  ]

################################################################################
# User sub-class
################################################################################

class MailUser(User):

  # called on object init; the following are already created by __init__:
  #   self.protocol = (Protocol) name of this User's protocol as a str
  #   self.typ = (int) either Message.PRIVATE or Message.GROUP
  #   self.real = (User) the "real" User behind this user (defaults to self)
  # @param user (object) a full username
  def parse(self,user):
    self.user = user

  # @return (str) the username in private chat or the nick name in a room
  def get_name(self):
    return self.user

  # @return (str) the username without resource identifier
  def get_base(self):
    return self.user

  # @param other (object) you must check for class equivalence
  # @return (bool) True if self==other (including resource)
  def __eq__(self,other):
    if not isinstance(other,MailUser):
      return False
    return self.user==other.user

  # @return (str) the full username
  def __str__(self):
    return self.user

################################################################################
# Room class
################################################################################

class MailRoom(Room):

  # called on object init; the following are already created by __init__:
  #   self.protocol = name of this Room's protocol as a str
  #   self.nick = the nick name to use in the room (defaults to None)
  #   self.pword = the password for this room (defaults to None)
  # @param name (object) a full roomid
  def parse(self,name):
    self.name = name

  # the return value must be the same for equal Rooms and unique for different
  # @return (str) the name of this Room
  def get_name(self):
    return self.name

  # @param other (object) you must check for class equivalence
  # @return (bool) true if other is the same room (ignore nick/pword if present)
  def __eq__(self,other):
    if not isinstance(other,MailRoom):
      return False
    return self.name==other.name

################################################################################
# Protocol sub-class
################################################################################

class MailProtocol(Protocol):

  # called on bot init; the following are already created by __init__:
  #   self.bot = SibylBot instance
  #   self.log = the logger you should use
  def setup(self):

    server = self.opt('email.address').split('@')[-1]
    self.imap_serv = (self.opt('email.imap') or ('imap.'+server))
    self.thread = IMAPThread(self)
    self.thread.start()
    self.smtp_serv = (self.opt('email.smtp') or ('smtp.'+server))
    self.smtp = None

  # @raise (ConnectFailure) if can't connect to server
  # @raise (AuthFailure) if failed to authenticate to server
  def connect(self):

    # we use IMAP to get new messages from the server
    # it runs in its own thread, appending messages asynchronously to a Queue
    self.log.debug('Attempting IMAP connection')
    self._connect_imap()
    self.log.info('IMAP successful')

    # we use SMTP to send emails
    self.log.debug('Attempting SMTP connection')
    self._connect_smtp()
    self.log.info('SMTP successful')

  # @return (bool) True if we are connected to the server
  def is_connected(self):
    return self.thread.imap is not None

  # receive/process messages and call bot._cb_message()
  # must ignore msgs from myself and from users not in any of our rooms
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @raise (PingTimeout) if implemented
  # @raise (ConnectFailure) if disconnected
  # @raise (ServerShutdown) if server shutdown
  def process(self):

    # every time SibylBot calls process(), this method synchronously checks for
    # new messages that the IMAPThread added while we were doing other things
    while not self.thread.msgs.empty():

      # check if there was a problem connecting and raise it syncronously
      mail = self.thread.msgs.get()
      if isinstance(mail,Exception):
        raise mail

      # parse the sender
      frm = email.utils.parseaddr(mail['From'])[1]
      user = MailUser(self,frm)

      # handle multi-part messages
      body = mail.get_payload()
      if isinstance(body,list):
        for b in body:
          if b.get_content_type()=='plain':
            body = b.replace('\r','').strip()
      if isinstance(body,list):
        self.log.warning('Ignoring multi-part from "%s"; no plaintext' % frm)
        self.send('Unable to process multi-part message; no plaintext',user)
        return

      # check for authentication key if configured
      if self.opt('email.key') and self.opt('email.key').get() not in body:
        self.log.warning('Invalid key from "%s"; dropping message' % user)
        self.send('Invalid or missing key; commands forbidden',user)
        continue

      # finish parsing the e-mail and send it
      body = body.split('\n')[0].strip()
      msg = Message(user,body)
      ellip = ('...' if len(body)>20 else '')
      self.log.debug('Mail from "%s" with body "%.20s%s"' % (user,body,ellip))

      # pass the message on to the bot for command execution
      self.bot._cb_message(msg)

  # called when the bot is exiting for whatever reason
  # NOTE: sibylbot will already call part_room() on every room in get_rooms()
  def shutdown(self):
    pass

  # send a message to a user
  # @param mess (Message) message to be sent
  # @raise (ConnectFailure) if failed to send message
  # Check: get_emote()
  # REF: http://stackoverflow.com/a/14678470
  def send(self,mess):

    (text,to) = (mess.get_text(),mess.get_to())

    # SMTP connections are short-lived, so we might need to reconnect
    try:
      status = self.smtp.noop()[0]
    except:
      status = -1
    if status!=250:
      self._connect_smtp()

    msg = MIMEText(text)
    msg['Subject'] = 'Sibyl reply'
    msg['From'] = self.opt('email.address')
    msg['To'] = str(to)

    self.smtp.sendmail(msg['From'],msg['To'],msg.as_string())

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param mess (Message) the message to broadcast
  # @return (str,unicode) the text that was actually sent
  # Check: get_user(), get_users()
  def broadcast(self,mess):
    pass

  # join the specified room using the specified nick and password
  # @param room (Room) the room to join
  # @call bot._cb_join_room_success(room) on successful join
  # @call bot._cb_join_room_failure(room,error) on failed join
  def join_room(self,room):
    bot._cb_join_room_failure(room,'Not supported')

  # part the specified room
  # @param room (Room) the room to leave
  def part_room(self,room):
    pass

  # helper function for get_rooms() for protocol-specific flags
  # only needs to handle: FLAG_PARTED, FLAG_PENDING, FLAG_IN, FLAG_ALL
  # @param flag (int) one of Room.FLAG_* enums
  # @return (list of Room) rooms matching the flag
  def _get_rooms(self,flag):
    return []

  # @param room (Room) the room to query
  # @return (list of User) the Users in the specified room
  def get_occupants(self,room):
    return []

  # @param room (Room) the room to query
  # @return (str) the nick name we are using in the specified room
  def get_nick(self,room):
    return None

  # @param room (Room) the room to query
  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  def get_real(self,room,nick):
    return nick

  # @return (User) our username
  def get_user(self):
    return MailUser(self,self.opt('email.address'))

  # @param user (str) a user id to parse
  # @param typ (int) [Message.PRIVATE] either Message.GROUP or Message.PRIVATE
  # @param real (User) [self] the "real" user behind this user
  # @return (User) a new instance of this protocol's User subclass
  def new_user(self,user,typ=None,real=None):
    return MailUser(self,user,typ,real)

  # @param name (object) the identifier for this Room
  # @param nick (str) [None] the nick name to use in this Room
  # @param pword (str) [None] the password for joining this Room
  # @return (Room) a new instance of this protocol's Room subclass
  def new_room(self,name,nick=None,pword=None):
    return MailRoom(self,name,nick,pword)

################################################################################
# Helper functions
################################################################################

  # convenience function for connecting the IMAP thread
  def _connect_imap(self):
    self.thread.connect()

  # convenience function for connecting to the SMTP server
  def _connect_smtp(self):

    # all major email providers support SSL, so use it
    try:
      self.smtp = smtplib.SMTP(self.smtp_serv,port=587)
      self.smtp.starttls()
      self.smtp.ehlo()
    except:
      raise ConnectFailure

    # if the protocol raises AuthFailure, SibylBot will never try to reconnect
    try:
      self.smtp.login(self.opt('email.address'),self.opt('email.password'))
    except:
      raise AuthFailure

################################################################################
# IMAPThread class
################################################################################

class IMAPThread(Thread):

  def __init__(self,proto):

    super(IMAPThread,self).__init__()
    self.daemon = True

    self.proto = proto
    self.imap = None
    self.msgs = Queue()

  # this method is called when doing IMAPThread().start()
  # we will be using IMAP IDLE push notifications as described at:
  #   https://tools.ietf.org/html/rfc2177
  # which allows us to near-instantly respond to new messages without polling
  # REF: http://stackoverflow.com/a/18103279
  def run(self):

    while True:

      # reconnect logic is handled in SibylBot, until that happens do nothing
      if not self.imap:
        time.sleep(1)
        continue

      # wait for the server to send us a new notification (this command blocks)
      line = self.imap.readline().strip()

      # if the line is blank, the server closed the connection
      if not line:
        try:
          self.connect()

        # raising exceptions in a Thread is messy, so we'll queue it instead
        except ProtocolError as e:
          self.imap = None
          self.msgs.put(e)

      # if the line ends with "EXISTS" then there is a new message waiting
      elif line.endswith('EXISTS'):

        # to end the IDLE state and actually get the message we issue "DONE"
        self.cmd('DONE')

        # after we get the new message(s) and Queue them, we enter IDLE again
        self.get_mail()
        self.cmd('IDLE')

  def connect(self):

    try:
      self.imap = imaplib.IMAP4_SSL(self.proto.imap_serv)
    except:
      raise ConnectFailure

    try:
      self.imap.login(self.proto.opt('email.address'),
        self.proto.opt('email.password'))
    except:
      raise AuthFailure

    # we have to specify which Inbox to use, and then enter the IDLE state
    self.imap.select()
    self.cmd('IDLE')

  # @param s (str) the SMTP command to send
  def cmd(self,s):
    self.imap.send("%s %s\r\n"%(self.imap._new_tag(),s))

  def get_mail(self):

    # only look at messages that don't have the "\\Seen" flag
    (status,nums) = self.imap.search('utf8','UNSEEN')

    # get new messages and add them to our Queue
    for n in nums[0].split(' '):
      msg = self.imap.fetch(n,'(RFC822)')[1][0][1]
      self.msgs.put(email.message_from_string(msg))

      # flag messages for deletion if configured to do so
      if self.proto.opt('email.delete'):
        self.imap.store(n,'+FLAGS','\\Deleted')

    # this tells the server to actually delete all flagged messages
    self.imap.expunge()
