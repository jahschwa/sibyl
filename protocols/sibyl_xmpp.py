# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2020 Joshua Haas <jahschwa.com>
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
###############################################################################

import logging

from slixmpp import ClientXMPP, JID as SlixJID

from sibyl.lib.decorators import botconf
from sibyl.lib.protocol import User, Room, Message, Protocol
from sibyl.lib.util import broadcast

###############################################################################
# Config options
###############################################################################

@botconf
def conf(bot):
  return [
    {'name': 'username', 'req': True},
    {'name': 'password', 'req': True},
    {'name': 'resource', 'default': 'sibyl'},
    {'name': 'server', 'default': None},
    {'name': 'port', 'default': 5222, 'parse': bot.conf.parse_int},
    {'name': 'ping_freq', 'default': 60, 'parse': bot.conf.parse_int},
    {'name': 'ping_timeout', 'default': 3, 'parse': bot.conf.parse_int},
    {'name': 'debug', 'default': False, 'parse': bot.conf.parse_bool},
    {'name': 'priv_domain', 'default': True, 'parse': bot.conf.parse_bool}
]

###############################################################################
# User sub-class
###############################################################################

class JID(User):

  # called on object init; the following are already created by __init__:
  #   self.protocol = (Protocol) name of this User's protocol as a str
  #   self.typ = (int) either Message.PRIVATE or Message.GROUP
  #   self.real = (User) the "real" User behind this user (defaults to self)
  # @param user (object) a full username
  def parse(self, user):

    # format for a JID is: node@domain/resource
    # for private chat this looks like: user@domain/resource
    # for group chat this looks like: room@domain/nick

    if isinstance(user, str):
      user = SlixJID(user)
    self.jid = user

  # @return (str) the username in private chat or the nick name in a room
  def get_name(self):

    if self.typ == Message.GROUP:
      return self.jid.resource
    return self.jid.node

  # @return (str) the username without resource identifier
  def get_base(self):

    if self.typ == Message.GROUP:
      return self.jid.full
    return self.jid.bare

  # @return (str) the full username
  def __str__(self):

    return self.jid.full

###############################################################################
# Room class
###############################################################################

class MUC(Room):

  # called on object init; the following are already created by __init__:
  #   self.protocol = name of this Room's protocol as a str
  #   self.nick = the nick name to use in the room (defaults to None)
  #   self.pword = the password for this room (defaults to None)
  # @param name (object) a full roomid
  def parse(self, room):

    if isinstance(room, JID):
      room = SlixJID(room.get_base())
    elif isinstance(room, str):
      room = SlixJID(room.split('/')[0])
    self.jid = room

  # the return value must be the same for equal Rooms and unique for different
  # @return (str) the name of this Room
  def get_name(self):

    return str(self.jid)

###############################################################################
# Protocol sub-class
###############################################################################

class XMPP(Protocol):

  HANDLER_PREFIX = '_cb_'

  PLUGIN_FMT = 'xep_{:0>4d}'
  PLUGIN_PREFIX = 'plug_'
  PLUGINS = {
    45: 'muc',
  }

  MSG_TYPES = {
    'presence': Message.STATUS,
    'chat': Message.PRIVATE,
    'groupchat': Message.GROUP,
    'error': Message.ERROR,
  }

  EMOTE_PREFIX = '/me '

  # called on bot init; the following are guaranteed to exist:
  #   self.bot = SibylBot instance
  #   self.log = the logger you should use
  def setup(self):

    self.jid = self.new_user(self.opt('xmpp.username'))
    self.events = {}

    if not self.opt('xmpp.debug'):
      logging.getLogger('slixmpp').setLevel(logging.ERROR)

    self.client = ClientXMPP(
      jid = self.jid.jid,
      password = self.opt('xmpp.password')
    )

    for name in dir(self):
      if name.startswith(XMPP.HANDLER_PREFIX):
        handler = name.replace(XMPP.HANDLER_PREFIX, '')
        self.client.add_event_handler(handler, self.make_cb(handler))
        self.events[handler] = False

    self.plugins = {}
    for (num, name) in XMPP.PLUGINS.items():
      xep = XMPP.PLUGIN_FMT.format(num)
      self.client.register_plugin(xep)
      setattr(self, XMPP.PLUGIN_PREFIX + name, self.client.plugin[xep])

  # @raise (ConnectFailure) if can't connect to server
  # @raise (AuthFailure) if failed to authenticate to server
  def _connect(self):

    self.clear_events()

    server = self.opt('xmpp.server') or self.jid.jid.domain
    self.client.connect(address=(server, self.opt('xmpp.port')))

    self.wait(connected=None, connection_failed=self.ConnectFailure)
    self.wait(auth_success=None, failed_auth=self.AuthFailure)
    self.wait(session_start=None, session_end=self.ConnectFailure)

  # @return (bool) True if we are connected to the server
  def is_connected(self):

    if not self.events['connected']:
      return False

    return not any(
      self.events[e] for e in ('connection_failed', 'disconnected')
    )

  # receive/process messages and call bot._cb_message()
  # must ignore msgs from myself and from users not in any of our rooms
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @raise (PingTimeout) if implemented
  # @raise (ConnectFailure) if disconnected
  # @raise (ServerShutdown) if server shutdown
  def process(self):

    self.client.process(timeout=0.1)

  # called when the bot is exiting for whatever reason
  def shutdown(self):

    for room in self.get_rooms():
      self.part_room(room)
    self.client.disconnect()

  # send a message to a user
  # @param mess (Message) message to be sent
  # @raise (ConnectFailure) if failed to send message
  # Check: get_emote()
  def send(self, mess):

    (text, to) = (mess.get_text(), mess.get_to())

    if mess.get_emote():
      text = '/me ' + mess.get_text()

    typ = 'groupchat' if isinstance(to, Room) else 'chat'

    self.client.send_message(to.jid, text, mtype=typ)

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param mess (Message) the message to broadcast
  # @return (str) the text that was actually sent
  # Check: get_user(), get_users()
  def broadcast(self, mess):

    room = mess.get_to()

    my_room_jid = '{}/{}'.format(room.get_name(), self.get_nick(room))
    me = self.new_user(my_room_jid, typ=Message.GROUP)

    s = broadcast(mess, skip=me)

    self.send(Message(self.jid, s, to=room))

    return s

  # join the specified room using the specified nick and password
  # @param room (Room) the room to join
  # @call bot._cb_join_room_success(room) on successful join
  # @call bot._cb_join_room_failure(room, error) on failed join
  def join_room(self, room):

    self.plug_muc.join_muc(
      room.jid,
      room.get_nick() or self.opt('nick_name'),
      password = room.get_password(),
      wait = True
    )
    self.bot._cb_join_room_success(room)

  # part the specified room
  # @param room (Room) the room to leave
  def part_room(self, room):

    self.plug_muc.leave_muc(room.jid, self.get_nick(room))

  # helper function for get_rooms() for protocol-specific flags
  # only needs to handle: FLAG_PARTED, FLAG_PENDING, FLAG_IN, FLAG_ALL
  # @param flag (int) one of Room.FLAG_* enums
  # @return (list of Room) rooms matching the flag
  def _get_rooms(self, flag):

    lookup = {
      Room.FLAG_PARTED: [],
      Room.FLAG_PENDING: [],
      Room.FLAG_IN: self.plug_muc.get_joined_rooms,
      Room.FLAG_ALL: self.plug_muc.get_joined_rooms,
    }

    rooms = lookup[flag]
    if not isinstance(rooms, list):
      rooms = rooms()

    return [r if isinstance(r, Room) else self.new_room(r) for r in rooms]

  # @param room (Room) the room to query
  # @return (list of User) the Users in the specified room
  def get_occupants(self, room):

    return [
      self.get_real(room, nick)
      for nick in self.plug_muc.get_roster(room.jid)
    ]

  # @param room (Room) the room to query
  # @return (str) the nick name we are using in the specified room
  def get_nick(self, room):

    return SlixJID(self.plug_muc.get_our_jid_in_room(room.jid)).resource

  # @param room (Room) the room to query
  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  def get_real(self, room, nick):

    name = room.get_name()
    real = self.plug_muc.get_jid_property(name, nick, 'jid')
    if real:
      return self.new_user(real)
    return self.new_user(name + '/' + nick, typ=Message.GROUP)

  # @return (User) our username
  def get_user(self):

    return self.jid

  # @param user (str) a user id to parse
  # @param typ (int) [Message.PRIVATE] either Message.GROUP or Message.PRIVATE
  # @param real (User) [self] the "real" user behind this user
  # @return (User) a new instance of this protocol's User subclass
  def new_user(self, user, typ=None, real=None):

    return JID(self, user, typ, real)

  # @param name (object) the identifier for this Room
  # @param nick (str) [None] the nick name to use in this Room
  # @param pword (str) [None] the password for joining this Room
  # @return (Room) a new instance of this protocol's Room subclass
  def new_room(self, name, nick=None, pword=None):

    return MUC(self, name, nick, pword)

###############################################################################
# Helper functions
###############################################################################

  def make_cb(self, name):

    func = getattr(self, XMPP.HANDLER_PREFIX + name, None)

    def wrapper(*args, **kwargs):

      result = None if not func else func(*args, **kwargs)
      self.events[name] = True
      return result

    return wrapper

  def clear_events(self):

    self.events = {event: False for event in self.events}

  def wait(self, **events):

    while not any(self.events[event] for event in events):
      self.process()

    for (event, ex) in events.items():
      if ex and self.events[event]:
        raise ex

###############################################################################
# Callbacks
###############################################################################

  def _cb_connected(self, event):
    pass

  def _cb_connection_failed(self, event):
    pass

  def _cb_disconnected(self, event):
    pass

  def _cb_auth_success(self, event):
    pass

  def _cb_failed_auth(self, event):
    pass

  def _cb_session_start(self, event):

    self.client.send_presence()
    self.client.get_roster()

  def _cb_presence(self, event):
    pass

  def _cb_session_end(self, event):
    pass

  def _cb_stream_error(self, event):
    pass

  def _cb_message(self, event):

    (typ, frm, body) = (event[x] for x in ('type', 'from', 'body'))
    frm = self.new_user(frm)
    (room, real, emote) = (None, None, False)

    if frm.get_base() == self.jid.get_base() or body is None:
      return

    if typ not in ('groupchat', 'chat'):
      self.log.debug('unhandled message type: {}'.format(typ))

    if typ == 'groupchat':
      room = self.new_room(frm)
      if room in self.get_rooms() and frm.jid.resource == self.get_nick(room):
        return

    txt = body if len(body) < 32 else body[:32] + '...'
    self.log.debug('Got {} from {}: "{}"'.format(typ, frm, txt))

    typ = XMPP.MSG_TYPES[typ]
    frm.set_real(self.get_real(room, frm.jid.resource))

    if body.startswith(XMPP.EMOTE_PREFIX):
      body = body[len(XMPP.EMOTE_PREFIX):].lstrip()
      emote = True

    self.bot._cb_message(Message(frm, body, typ=typ, room=room, emote=emote))

  def _cb_groupchat_invite(self, event):
    pass
