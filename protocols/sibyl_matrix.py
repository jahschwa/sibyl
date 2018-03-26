# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2017 Joshua Haas <haas.josh.a@gmail.com>
# Copyright (c) 2016-2017 Jonathan Frederickson <jonathan@terracrypt.net>
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

from Queue import Queue
from urlparse import urlparse
import traceback, datetime, pytz

from sibyl.lib.protocol import User,Room,Message,Protocol

from sibyl.lib.decorators import botconf

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError, MatrixHttpApi
from matrix_client.errors import MatrixHttpLibError
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
    {"name": "server", "req": True},
    {"name": "debug", "req": False, "default": False},
    # Valid values for join_on_invite are reject, accept, domain
    # reject: Don't accept any invites received
    # accept: Join any room when receiving an invite
    # domain: Only join rooms on invite if the inviter is on the same HS
    {"name": "join_on_invite", "req": False, "default": "reject"}
  ]

################################################################################
# User sub-class
################################################################################

class MatrixUser(User):

  # called on object init; the following are already created by __init__:
  #   self.protocol = (Protocol) name of this User's protocol as a str
  #   self.typ = (int) either Message.PRIVATE or Message.GROUP
  #   self.real = (User) the "real" User behind this user (defaults to self)
  # @param user (object) a full username
  def parse(self,user):
    if(isinstance(user,mxUser.User)):
      self.user = user
    elif(isinstance(user,basestring)):
      self.user = self.protocol.client.get_user(user)
    else:
      raise TypeError("User parameter to parse must be a string")

  # @return (str) the username in private chat or the nick name in a room
  def get_name(self):
    return self.user.get_display_name() or self.user.user_id

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

################################################################################
# Room sub-class
################################################################################

class MatrixRoom(Room):

  # called on object init; the following are already created by __init__:
  #   self.protocol = name of this Room's protocol as a str
  #   self.nick = the nick name to use in the room (defaults to None)
  #   self.pword = the password for this room (defaults to None)
  # @param name (object) a full roomid
  def parse(self,name):
    if(isinstance(name,mxRoom.Room)):
      self.room = room
    elif(isinstance(name,basestring)):
      self.room = mxRoom.Room(self.protocol.client,name) # [TODO] Assumes a room ID for now
    else:
      raise TypeError("User parameter to parse must be a string")

  # the return value must be the same for equal Rooms and unique for different
  # @return (str) the name of this Room
  def get_name(self):
    return self.room.room_id

  # @param other (object) you must check for class equivalence
  # @return (bool) true if other is the same room (ignore nick/pword if present)
  def __eq__(self,other):
    if(isinstance(other,MatrixRoom)):
      return self.get_name() == other.get_name()
    else:
      return False

################################################################################
# Protocol sub-class
################################################################################

class MatrixProtocol(Protocol):

  # List of occupants in each room
  # Used to avoid having to re-request the list of members each time
  room_occupants = {}
  # Keep track of when we joined rooms this session
  # Used to filter out historical messages after accepting room invites
  join_timestamps = {}

  # called on bot init; the following are already created by __init__:
  #   self.bot = SibylBot instance
  #   self.log = the logger you should use
  def setup(self):
    self.rooms = {}
    self.bot.add_var("credentials",persist=True)

    # Incoming message queue - messageHandler puts messages in here and
    # process() looks here periodically to send them to sibyl
    self.msg_queue = Queue()

    # Create a client in setup() because we might use self.client before
    # connect() is called
    homeserver = self.opt('matrix.server')
    self.client = MatrixClient(homeserver)

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
      if(self.bot.credentials and self.bot.credentials[0] == user):
        self.client = MatrixClient(homeserver, user_id=user, token=self.bot.credentials[1])
      # Otherwise, log in with the configured username and password
      else:
        token = self.client.login_with_password(user,pw)
        self.bot.credentials = (user, token)

      self.rooms = self.client.get_rooms()
      self.log.debug("Already in rooms: %s" % self.rooms)

      # Connect to Sibyl's message callback
      self.client.add_listener(self.messageHandler)
      self.client.add_invite_listener(self.inviteHandler)

      self.log.debug("Starting Matrix listener thread")
      self.client.start_listener_thread(exception_handler=self._matrix_exception_handler)

    except MatrixRequestError as e:
      if(e.code in [401, 403]):
        self.log.debug("Credentials incorrect! Maybe your access token is outdated?")
        raise self.AuthFailure
      else:
        if(self.opt('matrix.debug')):
          tb = traceback.format_exc()
          self.log.debug(tb)
        self.log.debug("Failed to connect to homeserver!")
        raise self.ConnectFailure
    except MatrixHttpLibError as e:
      self.log.error("Failed to connect to homeserver!")
      self.log.debug("Received error:" + str(e))
      raise self.ConnectFailure

  def _matrix_exception_handler(self, e):
    self.msg_queue.put(e)

  # receive/process messages and call bot._cb_message()
  # must ignore msgs from myself and from users not in any of our rooms
  # @call bot._cb_message(Message) upon receiving a valid status or message
  # @raise (PingTimeout) if implemented
  # @raise (ConnectFailure) if disconnected
  # @raise (ServerShutdown) if server shutdown
  def process(self):
    while(not self.msg_queue.empty()):
      next = self.msg_queue.get()
      if(isinstance(next, Message)):
        self.log.debug("Placing message into queue: " + next.get_text())
        self.bot._cb_message(next)
      elif(isinstance(next, MatrixHttpLibError)):
        self.log.debug("Received error from Matrix SDK, stopping listener thread: " + str(next))
        self.client.stop_listener_thread()
        raise self.ConnectFailure("Connection error returned by requests library: " + str(next))


  def messageHandler(self, msg):
    if(self.opt('matrix.debug')):
      self.log.debug(str(msg))

    try:
      # Create a new Message to send to Sibyl
      u = self.new_user(msg['sender'], Message.GROUP)
      r = self.new_room(msg['room_id'])

      if(r in self.join_timestamps
         and datetime.datetime.fromtimestamp(msg['origin_server_ts']/1000, pytz.utc) < self.join_timestamps[r]):
        self.log.info('Message received in {} from before room join, ignoring'.format(msg['room_id']))
        return None

      if('msgtype' in msg['content']):
        msgtype = msg['content']['msgtype']

        if(msgtype == 'm.text'):
          m = Message(u, msg['content']['body'], room=r, typ=Message.GROUP)
          self.log.debug('Handling m.text: ' + msg['content']['body'])
          self.msg_queue.put(m)

        elif(msgtype == 'm.emote'):
          m = Message(u, msg['content']['body'], room=r, typ=Message.GROUP,
          emote=True)
          self.log.debug('Handling m.emote: ' + msg['content']['body'])
          self.msg_queue.put(m)

        elif(msgtype == 'm.image' or msgtype == 'm.audio' or msgtype == 'm.file' or msgtype == 'm.video'):
          media_url = urlparse(msg['content']['url'])
          http_url = self.client.api.base_url + "/_matrix/media/r0/download/{0}{1}".format(media_url.netloc, media_url.path)
          if(msgtype == 'm.image'):
            body = "{0} uploaded {1}: {2}".format(msg['sender'], msg['content'].get('body', 'an image'), http_url)
          elif(msgtype == 'm.audio'):
            body = "{0} uploaded {1}: {2}".format(msg['sender'], msg['content'].get('body', 'an audio file'), http_url)
          elif(msgtype == 'm.video'):
            body = "{0} uploaded {1}: {2}".format(msg['sender'], msg['content'].get('body', 'a video file'), http_url)
          elif(msgtype == 'm.file'):
            body = "{0} uploaded {1}: {2}".format(msg['sender'], msg['content'].get('body', 'a file'), http_url)
          m = Message(u, body, room=r, typ=Message.GROUP)
          self.log.debug("Handling " + msgtype + ": " + body)
          self.msg_queue.put(m)

        elif(msgtype == 'm.location'):
          body = "{0} sent a location: {1}".format(msg['sender'], msg['content']['geo_uri'])
          m = Message(u, body, room=r, typ=Message.GROUP)
          self.log.debug('Handling m.location: ' + body)
          self.msg_queue.put(m)


        else:
          self.log.debug('Not handling message, unknown msgtype')

      elif('membership' in msg):
        if(msg['membership'] == 'join'):
          self.room_occupants[r].add(self.new_user(msg['state_key'], Message.GROUP))
        elif(msg['membership'] == 'leave'):
          self.room_occupants[r].remove(self.new_user(msg['state_key'], Message.GROUP))

    except KeyError as e:
      self.log.debug("Incoming message did not have all required fields: " + e.message)


  def inviteHandler(self, room_id, state):
    join_on_invite = self.opt('matrix.join_on_invite')

    invite_events = [x for x in state['events'] if x['type'] == 'm.room.member'
                     and x['state_key'] == str(self.get_user())
                     and x['content']['membership'] == 'invite']
    if(len(invite_events) != 1):
      raise KeyError("Something's up, found more than one invite state event for " + room_id)

    inviter = invite_events[0]['sender']
    inviter_domain = inviter.split(':')[1]
    my_domain = str(self.get_user()).split(':')[1]

    if(join_on_invite == 'accept' or (join_on_invite == 'domain' and inviter_domain == my_domain)):
      self.log.debug('Joining {} on invite from {}'.format(room_id, inviter))
      self.join_room(MatrixRoom(self, room_id))

    elif(join_on_invite == 'domain' and inviter_domain != my_domain):
      self.log.debug("Received invite for {} but inviter {} is on a different homeserver").format(room_id, inviter)

    else:
      self.log.debug("Received invite for {} from {} but join_on_invite is disabled".format(room_id, inviter))


  # called when the bot is exiting for whatever reason
  # NOTE: sibylbot will already call part_room() on every room in get_rooms()
  def shutdown(self):
    pass

  # send a message to a user
  # @param mess (Message) message to be sent
  # @raise (ConnectFailure) if failed to send message
  # Check: get_emote()
  def send(self,mess):
    (text,to) = (mess.get_text(),mess.get_to())
    if(mess.get_emote()):
      to.room.send_emote(text)
    else:
      to.room.send_text(text)

  # send a message with text to every user in a room
  # optionally note that the broadcast was requested by a specific User
  # @param mess (Message) the message to broadcast
  # @return (str,unicode) the text that was actually sent
  # Check: get_user(), get_users()
  def broadcast(self,mess):
    """send a message to every user in a room"""

    (text,room,frm) = (mess.get_text(),mess.get_to(),mess.get_user())
    users = self.get_occupants(room)+(mess.get_users() or [])

    # Matrix has no built-in broadcast, so we'll just highlight everyone
    s = 'all: %s --- ' % text
    if frm:
      self.log.debug('Broadcast message from: ' + str(frm))
      s += frm.get_name()+' --- '

    me = self.get_user()
    names = [u.get_name() for u in users if (u!=me and (not frm or u!=frm))]
    s += ', '.join(set(names))

    self.send(Message(self.get_user(),s,to=room))
    return s

  # join the specified room using the specified nick and password
  # @param room (Room) the room to join
  # @call bot._cb_join_room_success(room) on successful join
  # @call bot._cb_join_room_failure(room,error) on failed join
  def join_room(self,room):
    try:
      res = self.client.join_room(room.room.room_id)
      self.bot._cb_join_room_success(room)
      self.join_timestamps[room] = datetime.datetime.now(pytz.utc)
    except MatrixRequestError as e:
      self.bot._cb_join_room_failure(room, e.message)

  # part the specified room
  # @param room (Room) the room to leave
  def part_room(self,room):
    raise NotImplementedError

  # helper function for get_rooms() for protocol-specific flags
  # only needs to handle: FLAG_PARTED, FLAG_PENDING, FLAG_IN, FLAG_ALL
  # @param flag (int) one of Room.FLAG_* enums
  # @return (list of Room) rooms matching the flag
  def _get_rooms(self,flag):
    mxrooms = self.client.get_rooms()
    return [self.new_room(mxroom) for mxroom in mxrooms]


  # @param room (Room) the room to query
  # @return (list of User) the Users in the specified room
  def get_occupants(self,room):
    if(room in self.room_occupants):
      return list(self.room_occupants[room])
    else:
      memberdict = room.room.get_joined_members()
      users = [ self.new_user(x) for x in memberdict ]
      self.room_occupants[room] = set(users)
      return users

  # @param room (Room) the room to query
  # @return (str) the nick name we are using in the specified room
  def get_nick(self,room):
    return self.get_user().get_name() # TODO: per-room nicknames

  # @param room (Room) the room to query
  # @param nick (str) the nick to examine
  # @return (User) the "real" User behind the specified nick/room
  def get_real(self,room,nick):
    raise NotImplementedError

  # @return (User) our username
  def get_user(self):
    return MatrixUser(self,self.opt('matrix.username'),Message.GROUP)

  # @param user (str) a user id to parse
  # @param typ (int) either Message.GROUP or Message.PRIVATE
  # @param real (User) [self] the "real" user behind this user
  # @return (User) a new instance of this protocol's User subclass
  def new_user(self,user,typ=None,real=None):
    return MatrixUser(self,user,typ,real)

  # @param name (object) the identifier for this Room
  # @param nick (str) [None] the nick name to use in this Room
  # @param pword (str) [None] the password for joining this Room
  # @return (Room) a new instance of this protocol's Room subclass
  def new_room(self,room_id_or_alias,nick=None,pword=None):
    return MatrixRoom(self,room_id_or_alias,nick,pword)

################################################################################
# Helper functions
################################################################################
