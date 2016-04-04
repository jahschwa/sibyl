#!/usr/bin/python
# -*- coding: utf-8 -*-

# JabberBot: A simple jabber/xmpp bot framework
# Copyright (c) 2007-2012 Thomas Perl <thp.io/about>
# $Id: d1c7090edd754ff0da8ef4eb10d4b46883f34b9f $
#
# This program is free software; you can redistribute it and/or modify
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

################################################################################
#                                                                              #
# Modified by Joshua Haas for use with Sibyl                                   #
# https://github.com/TheSchwa/sibyl                                            #
#                                                                              #
################################################################################

"""
A framework for writing Jabber/XMPP bots and services

The JabberBot framework allows you to easily write bots
that use the XMPP protocol. You can create commands by
decorating functions in your subclass or customize the
bot's operation completely. MUCs are also supported.
"""

import os,re,sys,time,inspect,imp,logging,traceback

try:
  import xmpp
except ImportError:
  print >> sys.stderr, """
  You need to install xmpppy from http://xmpppy.sf.net/.
  On Debian-based systems, install the python-xmpp package.
  """
  sys.exit(-1)

from xmpp.protocol import SystemShutdown

# Will be parsed by setup.py to determine package metadata
__author__ = 'Thomas Perl <m@thp.io>'
__version__ = '0.16'
__website__ = 'http://thp.io/2007/python-jabberbot/'
__license__ = 'GNU General Public License version 3 or later'

################################################################################
# Decorators                                                                   #
################################################################################

def botcmd(func,name=None):
  """Decorator for bot chat commands"""

  setattr(func, '_jabberbot_dec_chat', True)
  setattr(func, '_jabberbot_dec_chat_name', name or func.__name__)
  return func

def botfunc(func):
  """Decorator for bot helper functions"""

  setattr(func, '_jabberbot_dec_func', True)
  return func

def botinit(func):
  """Decorator for bot initialisation hooks"""

  setattr(func, '_jabberbot_dec_init', True)
  return func

def botmucs(func):
  """Decorator for success joining a room hooks"""

  setattr(func, '_jabberbot_dec_mucs', True)
  return func

def botmucf(func):
  """Decorator for failure to join a room hooks"""

  setattr(func, '_jabberbot_dec_mucf', True)
  return func

def botmsg(func):
  """Decorator for message received hooks"""

  setattr(func, '_jabberbot_dec_msg', True)
  return func

def botpres(func):
  """Decorator for presence received hooks"""

  setattr(func, '_jabberbot_dec_pres', True)
  return func

################################################################################
# Custom exceptions                                                            #
################################################################################

class PingTimeout(Exception):
  pass

class ConnectFailure(Exception):
  pass

class AuthFailure(Exception):
  pass

class MUCJoinFailure(Exception):
  pass

################################################################################
# JabberBot class                                                              #
################################################################################

class JabberBot(object):
  # Show types for presence
  AVAILABLE, AWAY, CHAT = None, 'away', 'chat'
  DND, XA, OFFLINE = 'dnd', 'xa', 'unavailable'

  # UI-messages (overwrite to change content)
  MSG_UNKNOWN_COMMAND = 'Unknown command: "%(command)s". '\
    'Type "%(helpcommand)s" for available commands.'
  MSG_HELP_TAIL = 'Type %(helpcommand)s <command name> to get more info '\
    'about that specific command.'
  MSG_HELP_UNDEFINED_COMMAND = 'That command is not defined.'
  MSG_ERROR_OCCURRED = 'Sorry for your inconvenience. '\
    'An unexpected error occurred.'

  # MUC joining errors
  MUC_JOIN_ERROR = {'not-authorized'          : 'invalid password',
                    'forbidden'               : 'banned',
                    'item-not-found'          : 'room does not exist',
                    'not-allowed'             : 'room creation forbidden',
                    'not-acceptable'          : 'must use reserved nick',
                    'registration-required'   : 'not a member',
                    'conflict'                : 'nick in use',
                    'service-unavailable'     : 'room is full',
                    'remote-server-not-found' : 'server not found',
                    'timeout'                 : 'timeout'}

  # MUC status codes
  MUC_PARTED = -1
  MUC_OK = 0
  MUC_ERR = 1
  MUC_BANNED = 301
  MUC_KICKED = 307
  MUC_AFFIL = 321
  MUC_MEMBERS = 322
  MUC_SHUTDOWN = 332
  
################################################################################
# Init                                                                         #
################################################################################

  def __init__(self, username, password, res=None, debug=False, rooms=None,
      privatedomain=True, acceptownmsgs=False, handlers=None, cmd_dir='cmds',
      cmd_prefix=None, server=None, port=5222, ping_freq=300,
      ping_timeout=3, only_direct=True, reconnect_wait=60, catch_except=True):
    """Initializes the jabber bot and sets up commands.

    username and password should be clear ;)

    If res provided, res will be ressourcename,
    otherwise it defaults to classname of childclass

    If debug is True log messages of xmpppy will be printed to console.
    Logging of Jabberbot itself is NOT affected.

    If privatedomain is provided, it should be either
    True to only allow subscriptions from the same domain
    as the bot or a string that describes the domain for
    which subscriptions are accepted (e.g. 'jabber.org').

    If acceptownmsgs it set to True, this bot will accept
    messages from the same JID that the bot itself has. This
    is useful when using JabberBot with a single Jabber account
    and multiple instances that want to talk to each other.

    If handlers are provided, default handlers won't be enabled.
    Usage like: [('stanzatype1', function1), ('stanzatype2', function2)]
    Signature of function should be callback_xx(self, conn, stanza),
    where conn is the connection and stanza the current stanza in process.
    First handler in list will be served first.
    Don't forget to raise exception xmpp.NodeProcessed to stop
    processing in other handlers (see callback_presence)

    If cmd_prefix is set to a string different from '' (the empty
    string), it will require the commands to be prefixed with this text,
    e.g. cmd_prefix = '!' means: Type "!info" for the "info" command.
    """

    self.MUC_CODES = {self.MUC_PARTED   : ('parted',None),
                      self.MUC_OK       : ('OK',None),
                      self.MUC_ERR      : ('unknown',self.log.error),
                      self.MUC_BANNED   : ('banned',self.log.critical),
                      self.MUC_KICKED   : ('kicked',self.log.error),
                      self.MUC_AFFIL    : ('affiliation',self.log.info),
                      self.MUC_MEMBERS  : ('members-only',self.log.error),
                      self.MUC_SHUTDOWN : ('shutdown',self.log.error)}

    # XMPP JID
    if server is not None:
      self.__server = (server, port)
    else:
      self.__server = None
    self.__username = username
    self.__password = password
    
    self.jid = xmpp.JID(self.__username)
    self.res = (res or self.__class__.__name__)

    # General XMPP
    self.__status = None
    self.__threads = {}

    self.seen = {}
    self.conn = None
    self.roster = None

    # XMPP MUC stuff
    self.__lastjoin = 0
    self.__muc_pending = []

    self.rooms = rooms
    if not self.rooms:
      self.rooms = []
    self.real_jids = {}
    self.mucs = {}
    self.last_muc = None

    # Pinging
    self.__lastping = time.time()
    self.__ping_freq = ping_freq
    self.__ping_timeout = ping_timeout

    # Control
    self.__debug = debug
    self.__finished = False
    self.__show = None
    self.__handlers = (handlers or [('message', self.callback_message),
          ('presence', self.callback_presence)])

    self.log = logging.getLogger(__name__)
    self.catch_except = catch_except
    self.cmd_dir = os.path.abspath(cmd_dir)
    
    # User options
    self.__privatedomain = privatedomain
    self.__acceptownmsgs = acceptownmsgs
    self.__reconnect_wait = reconnect_wait

    self.only_direct = only_direct
    self.cmd_prefix = cmd_prefix

    # Load hooks from self.cmd_dir
    self.hooks = {x:{} for x in ['chat','init','mucs','mucf','msg','pres']}
    files = [x for x in os.listdir(self.cmd_dir) if x.endswith('.py')]
    
    for f in files:
      f = f.split('.')[0]
      found = imp.find_module(f,[self.cmd_dir])
      mod = imp.load_module(f,*found)
      self.__load_funcs(mod,f)
    self.__load_funcs(self,'jabberbot')

    # Run plugin init hooks
    self.__run_hooks('init')

  def __load_funcs(self,mod,fil):
    
    for (name,func) in inspect.getmembers(mod,inspect.isfunction):
      
      if getattr(func,'_jabberbot_dec_func',False):
        setattr(self,name,self.__bind(func))
        self.log.debug('Registered function: %s.%s' % (fil,name))

      for (hook,dic) in self.hooks.items():
        if getattr(func,'_jabberbot_dec_'+hook,False):
          fname = getattr(func,'_jabberbot_dec_'+hook+'_name',None)
          s = 'Registered %s command: %s.%s = %s' % (hook,fil,name,fname)
          if fname is None:
            fname = fil+'.'+name
            s = 'Registered %s hook: %s.%s' % (hook,fil,name)
          dic[fname] = self.__bind(func)
          self.log.debug(s)

  def __bind(self,func):

    return func.__get__(self,JabberBot)

  def __run_hooks(self,hook):
    
    for (name,func) in self.hooks[hook].items():
      self.log.debug('Running %s hook: %s' % (hook,name))
      func()

################################################################################
# Basic XMPP                                                                   #
################################################################################

  def _send_status(self):
    """Send status to everyone"""
    self.conn.send(xmpp.dispatcher.Presence(show=self.__show,
      status=self.__status))

  def __set_status(self, value):
    """Set status message.
    If value remains constant, no presence stanza will be send"""
    if self.__status != value:
      self.__status = value
      self._send_status()

  def __get_status(self):
    """Get current status message"""
    return self.__status

  status_message = property(fget=__get_status, fset=__set_status)

  def __set_show(self, value):
    """Set show (status type like AWAY, DND etc.).
    If value remains constant, no presence stanza will be send"""
    if self.__show != value:
      self.__show = value
      self._send_status()

  def __get_show(self):
    """Get current show (status type like AWAY, DND etc.)."""
    return self.__show

  status_type = property(fget=__get_show, fset=__set_show)

  def connect(self):
    """Connects the bot to server or returns current connection,
    send inital presence stanza
    and registers handlers
    """
    if not self.conn:
      self.log.debug('Attempting to connect using JID "%s"...' % self.jid)
      conn = xmpp.Client(self.jid.getDomain(), debug=self.__debug)

      #connection attempt
      if self.__server:
        conres = conn.connect(self.__server)
      else:
        conres = conn.connect()
      if not conres:
        raise ConnectFailure
      if conres != 'tls':
        self.log.warning('unable to establish secure connection '\
        '- TLS failed!')

      authres = conn.auth(self.jid.getNode(), self.__password, self.res)
      if not authres:
        raise AuthFailure
      if authres != 'sasl':
        self.log.warning("unable to perform SASL auth on %s. "\
        "Old authentication method used!" % self.jid.getDomain())

      # Connection established - save connection
      self.conn = conn

      # Register given handlers (TODO move to own function)
      for (handler, callback) in self.__handlers:
        self.conn.RegisterHandler(handler, callback)
        self.log.debug('Registered handler: %s' % handler)

      # Send initial presence stanza (say hello to everyone)
      self.conn.sendInitPresence()
      # Save roster and log Items
      self.roster = self.conn.Roster.getRoster()
      self.log.info('*** roster ***')
      for contact in self.roster.getItems():
        self.log.info('  %s' % contact)
      self.log.info('*** roster ***')

    return self.conn

################################################################################
# XEP-0045 Multi User Chat (MUC)                                               #
################################################################################

  def get_current_mucs(self):
    """return all mucs that we are currently in"""

    return [room for room in self.mucs if self.mucs[room]['status']==self.MUC_OK]

  def get_active_mucs(self):
    """return all mucs we are in or are trying to reconnect"""

    return [room for room in self.mucs if self.mucs[room]['status']!=self.MUC_PARTED]

  def get_inactive_mucs(self):
    """return all mucs that we are currently not in"""

    return [room for room in self.mucs if self.mucs[room]['status']!=self.MUC_OK]

  def get_default_nick(self):
    """Return a default nick name"""

    return self.__username.split('@')[0]

  def muc_join_room(self, room, username=None, password=None):
    """Join the specified multi-user chat room or changes nickname

    If username is NOT provided fallback to node part of JID"""

    for x in self.__muc_pending:
      if x[1]==room:
        return
    
    # TODO fix namespacestrings and history settings
    NS_MUC = 'http://jabber.org/protocol/muc'
    
    if username is None:
      username = self.get_default_nick()
    my_room_JID = '/'.join((room, username))
    pres = xmpp.Presence(to=my_room_JID)
    
    # request no history
    pres.setTag('x',namespace=NS_MUC).setTagData('history','',attrs={'maxchars':'0'})

    # handle MUC password
    if password is not None:
      pres.setTag('x', namespace=NS_MUC).setTagData('password', password)

    self.__muc_pending.append((pres,room,username,password))

  def _muc_join(self,pres,room,username,password):
    """join a muc and handle the result"""

    self.log.debug('Attempting to join room "%s"' % room)
    self.last_muc = room
    result = self.connect().SendAndWaitForResponse(pres)

    # result is None for timeout
    if not result:
      self.log.error('Error joining room "%s" (timeout)' % room)
      raise MUCJoinFailure('timeout')

    # check for error
    error = result.getError()
    if error:
      self.log.error('Error joining room "%s" (%s)' % (room,self.MUC_JOIN_ERROR[error]))
      raise MUCJoinFailure(error)

    # we joined successfully
    self.mucs[room] = {'pass':password,'nick':username,'status':self.MUC_OK}
    self.log.info('Success joining room "%s"' % room)

  def _muc_join_success(self,room):
    """execute callbacks on successfull MUC join"""
    
    self.__run_hooks('mucs')

  def _muc_join_failure(self,room,error):
    """execute callbacks on successfull MUC join"""
    
    self.__run_hooks('mucf')

  def muc_rejoin(self,room):
    """Rejoin the last joined room"""

    if not room:
      if not self.last_muc:
        raise RuntimeError('No room to rejoin; use muc_join_room() first')
      else:
        room = self.last_muc

    muc = self.mucs[room]
    self.muc_join_room(room,muc['nick'],muc['pass'])

  def muc_part_room(self, room, username=None, message=None):
    """Parts the specified multi-user chat"""

    if self.mucs[room]['status']==self.MUC_OK:
      if username is None:
        # TODO use xmpppy function getNode
        username = self.__username.split('@')[0]
      my_room_JID = '/'.join((room, username))
      pres = xmpp.Presence(to=my_room_JID)
      pres.setAttr('type', 'unavailable')
      if message is not None:
        pres.setTagData('status', message)
      self.connect().send(pres)
      
    self.mucs[room]['status'] = self.MUC_PARTED
    self.log.debug('Parted room "%s"' % room)

  def muc_set_role(self, room, nick, role, reason=None):
    """Set role to user from muc
    reason works only if defined in protocol
    Works only with sufficient rights."""
    NS_MUCADMIN = 'http://jabber.org/protocol/muc#admin'
    item = xmpp.simplexml.Node('item')
    item.setAttr('jid', jid)
    item.setAttr('role', role)
    iq = xmpp.Iq(typ='set', queryNS=NS_MUCADMIN, xmlns=None, to=room,
        payload=set([item]))
    if reason is not None:
      item.setTagData('reason', reason)
    self.connect().send(iq)

  def muc_kick(self, room, nick, reason=None):
    """Kicks user from muc
    Works only with sufficient rights."""
    self.muc_set_role(room, nick, 'none', reason)


  def muc_set_affiliation(self, room, jid, affiliation, reason=None):
    """Set affiliation to user from muc
    reason works only if defined in protocol
    Works only with sufficient rights."""
    NS_MUCADMIN = 'http://jabber.org/protocol/muc#admin'
    item = xmpp.simplexml.Node('item')
    item.setAttr('jid', jid)
    item.setAttr('affiliation', affiliation)
    iq = xmpp.Iq(typ='set', queryNS=NS_MUCADMIN, xmlns=None, to=room,
        payload=set([item]))
    if reason is not None:
      item.setTagData('reason', reason)
    self.connect().send(iq)

  def muc_ban(self, room, jid, reason=None):
    """Bans user from muc
    Works only with sufficient rights."""
    self.muc_set_affiliation(room, jid, 'outcast', reason)

  def muc_unban(self, room, jid):
    """Unbans user from muc
    User will not regain old affiliation.
    Works only with sufficient rights."""
    self.muc_set_affiliation(room, jid, 'none')

  def muc_set_subject(self, room, text):
    """Changes subject of muc
    Works only with sufficient rights."""
    mess = xmpp.Message(to=room)
    mess.setAttr('type', 'groupchat')
    mess.setTagData('subject', text)
    self.connect().send(mess)

  def muc_get_subject(self, room):
    """Get subject of muc"""
    pass

  def muc_room_participants(self, room):
    """Get list of participants """
    pass

  def muc_get_role(self, room, nick=None):
    """Get role of nick
    If nick is None our own role will be returned"""
    pass

  def muc_invite(self, room, jid, reason=None):
    """Invites user to muc.
    Works only if user has permission to invite to muc"""
    NS_MUCUSER = 'http://jabber.org/protocol/muc#user'
    invite = xmpp.simplexml.Node('invite')
    invite.setAttr('to', jid)
    if reason is not None:
      invite.setTagData('reason', reason)
    mess = xmpp.Message(to=room)
    mess.setTag('x', namespace=NS_MUCUSER).addChild(node=invite)
    self.log.error(mess)
    self.connect().send(mess)

################################################################################
# General XMPP                                                                 #
################################################################################

  def send_message(self, mess):
    """Send an XMPP message"""
    self.connect().send(mess)

  def send_tune(self, song, debug=False):
    """Set information about the currently played tune

    Song is a dictionary with keys: file, title, artist, album, pos, track,
    length, uri. For details see <http://xmpp.org/protocols/tune/>.
    """
    NS_TUNE = 'http://jabber.org/protocol/tune'
    iq = xmpp.Iq(typ='set')
    iq.setFrom(self.jid)
    iq.pubsub = iq.addChild('pubsub', namespace=xmpp.NS_PUBSUB)
    iq.pubsub.publish = iq.pubsub.addChild('publish',
      attrs={'node': NS_TUNE})
    iq.pubsub.publish.item = iq.pubsub.publish.addChild('item',
      attrs={'id': 'current'})
    tune = iq.pubsub.publish.item.addChild('tune')
    tune.setNamespace(NS_TUNE)

    title = None
    if 'title' in song:
      title = song['title']
    elif 'file' in song:
      title = os.path.splitext(os.path.basename(song['file']))[0]
    if title is not None:
      tune.addChild('title').addData(title)
    if 'artist' in song:
      tune.addChild('artist').addData(song['artist'])
    if 'album' in song:
      tune.addChild('source').addData(song['album'])
    if 'pos' in song and song['pos'] > 0:
      tune.addChild('track').addData(str(song['pos']))
    if 'time' in song:
      tune.addChild('length').addData(str(song['time']))
    if 'uri' in song:
      tune.addChild('uri').addData(song['uri'])

    if debug:
      self.log.info('Sending tune: %s' % iq.__str__().encode('utf8'))
    self.conn.send(iq)

  def send(self, user, text, in_reply_to=None, message_type='chat'):
    """Sends a simple message to the specified user."""
    mess = self.build_message(text)
    mess.setTo(user)

    if in_reply_to:
      mess.setThread(in_reply_to.getThread())
      mess.setType(in_reply_to.getType())
    else:
      mess.setThread(self.__threads.get(user, None))
      mess.setType(message_type)

    self.send_message(mess)

  def send_simple_reply(self, mess, text, private=False):
    """Send a simple response to a message"""
    self.send_message(self.build_reply(mess, text, private))

  def build_reply(self, mess, text=None, private=False):
    """Build a message for responding to another message.
    Message is NOT sent"""
    response = self.build_message(text)
    if private:
      response.setTo(mess.getFrom())
      response.setType('chat')
    else:
      response.setTo(mess.getFrom().getStripped())
      response.setType(mess.getType())
    response.setThread(mess.getThread())
    return response

  def build_message(self, text):
    """Builds an xhtml message without attributes.
    If input is not valid xhtml-im fallback to normal."""
    message = None  # init message variable
    # Try to determine if text has xhtml-tags - TODO needs improvement
    text_plain = re.sub(r'<[^>]+>', '', text)
    if text_plain != text:
      # Create body w stripped tags for reciptiens w/o xhtml-abilities
      # FIXME unescape &quot; etc.
      message = xmpp.protocol.Message(body=text_plain)
      # Start creating a xhtml body
      html = xmpp.Node('html', \
        {'xmlns': 'http://jabber.org/protocol/xhtml-im'})
      try:
        html.addChild(node=xmpp.simplexml.XML2Node( \
          "<body xmlns='http://www.w3.org/1999/xhtml'>" + \
          text.encode('utf-8') + "</body>"))
        message.addChild(node=html)
      except Exception, e:
        # Didn't work, incorrect markup or something.
        self.log.debug('An error while building a xhtml message. '\
        'Fallback to normal messagebody')
        # Fallback - don't sanitize invalid input. User is responsible!
        message = None
    if message is None:
      # Normal body
      message = xmpp.protocol.Message(body=text)
    return message

  def get_sender_username(self, mess):
    """Extract the sender's user name from a message"""
    type = mess.getType()
    jid = mess.getFrom()
    if type == "groupchat":
      username = jid.getResource()
    elif type == "chat":
      username = jid.getNode()
    else:
      username = ""
    return username

  def get_full_jids(self, jid):
    """Returns all full jids, which belong to a bare jid

    Example: A bare jid is bob@jabber.org, with two clients connected,
    which
    have the full jids bob@jabber.org/home and bob@jabber.org/work."""
    for res in self.roster.getResources(jid):
      full_jid = "%s/%s" % (jid, res)
      yield full_jid

  def status_type_changed(self, jid, new_status_type):
    """Callback for tracking status types (dnd, away, offline, ...)"""
    self.log.debug('user %s changed status to %s' % (jid, new_status_type))

  def status_message_changed(self, jid, new_status_message):
    """Callback for tracking status messages (the free-form status text)"""
    self.log.debug('user %s updated text to %s' %
      (jid, new_status_message))

  def broadcast(self, message, only_available=False):
    """Broadcast a message to all users 'seen' by this bot.

    If the parameter 'only_available' is True, the broadcast
    will not go to users whose status is not 'Available'."""
    for jid, (show, status) in self.seen.items():
      if not only_available or show is self.AVAILABLE:
        self.send(jid, message)

  def remove_prefix(self,text):
    """remove the command prefix from the given text"""

    if not self.cmd_prefix:
      return text
    if not text.startswith(self.cmd_prefix):
      return text
    return text[len(self.cmd_prefix):]

  def get_cmd(self,mess):
    """return the body of mess with nick and prefix removed, or None if invalid"""

    text = mess.getBody()
    frm = mess.getFrom()
    if not text:
      return None

    direct = False
    prefix = False

    # only direct logic
    room = frm.getStripped()
    if room in self.get_current_mucs() and text.lower().startswith(self.mucs[room]['nick'].lower()):
      text = ' '.join(text.split(' ',1)[1:])
      direct = True

    # command prefix logic
    text = self.remove_prefix(text)
    prefix = (text!=mess.getBody())

    if mess.getType()=='chat':
      return text
    else:
      if ((not self.only_direct) and (not self.cmd_prefix) or
          ((self.only_direct and direct) or (self.cmd_prefix and prefix))):
        return text
    return None

################################################################################
# Callbacks                                                                    #
################################################################################

  def callback_presence(self, conn, presence):

    jid, type_, show, status = presence.getFrom(), \
        presence.getType(), presence.getShow(), \
        presence.getStatus()

    # run plugin hooks
    self.__run_hooks('pres')

    # keep track of "real" JIDs in a MUC
    if len(self.get_current_mucs()) and jid.getStripped() in self.get_current_mucs():
      try:
        realjid = presence.getTag('x').getTag('item').getAttr('jid')
        self.real_jids[jid] = xmpp.protocol.JID(realjid)
        self.log.debug('JID: '+str(jid)+' = realJID: '+realjid)
      except:
        pass

    if self.jid.bareMatch(jid):
      # update internal status
      if type_ != self.OFFLINE:
        self.__status = status
        self.__show = show
      else:
        self.__status = ""
        self.__show = self.OFFLINE
      if not self.__acceptownmsgs:
        # Ignore our own presence messages
        return

    if type_ is None:
      # Keep track of status message and type changes
      old_show, old_status = self.seen.get(jid, (self.OFFLINE, None))
      if old_show != show:
        self.status_type_changed(jid, show)

      if old_status != status:
        self.status_message_changed(jid, status)

      self.seen[jid] = (show, status)
    elif type_ == self.OFFLINE and jid in self.seen:
      # Notify of user offline status change
      del self.seen[jid]
      self.status_type_changed(jid, self.OFFLINE)

    try:
      subscription = self.roster.getSubscription(unicode(jid.__str__()))
    except KeyError, e:
      # User not on our roster
      subscription = None
    except AttributeError, e:
      # Recieved presence update before roster built
      return

    if type_ == 'error':
      self.log.error(presence.getError())

    self.log.debug('Got presence: %s (type: %s, show: %s, status: %s, '\
      'subscription: %s)' % (jid, type_, show, status, subscription))

    # Catch kicked from the room
    room = jid.getStripped()
    if room in self.get_current_mucs() and jid.getResource()==self.mucs[room]['nick']:
      code = presence.getStatusCode()
      if code:
        code = int(code)
        if code not in self.MUC_CODES:
          code = 1
        self.mucs[room]['status'] = code
        self.__lastjoin = time.time()
        (text,func) = self.MUC_CODES[code]
        func('Forced from room "%s" (%s)' % (room,text))
        self.log.debug('Rejoining room "%s" in %i sec' % (room,self.__reconnect_wait))

    # If subscription is private,
    # disregard anything not from the private domain
    if self.__privatedomain and type_ in ('subscribe', 'subscribed', \
      'unsubscribe'):
      if self.__privatedomain == True:
        # Use the bot's domain
        domain = self.jid.getDomain()
      else:
        # Use the specified domain
        domain = self.__privatedomain

      # Check if the sender is in the private domain
      user_domain = jid.getDomain()
      if domain != user_domain:
        self.log.info('Ignoring subscribe request: %s does not '\
        'match private domain (%s)' % (user_domain, domain))
        return

    # Incoming subscription request
    if type_ == 'subscribe':
      # Authorize all subscription requests (we checked for domain above)
      self.roster.Authorize(jid)
      self._send_status()
    # Do nothing for 'subscribed' or 'unsubscribed'

  def callback_message(self, conn, mess):
    """Messages sent to the bot will arrive here.
    Command handling + routing is done in this function."""

    # Prepare to handle either private chats or group chats
    typ = mess.getType()
    jid = mess.getFrom()
    props = mess.getProperties()
    text = mess.getBody()
    username = self.get_sender_username(mess)
    private = False

    if typ not in ("groupchat", "chat"):
      self.log.debug("unhandled message type: %s" % typ)
      return

    # Account for MUC PM messages
    if (typ=='chat' and len(self.get_current_mucs())
        and jid.getStripped() in self.get_current_mucs()):
      private = True

    if typ=='groupchat':
      
      # Ignore messages from before we joined
      if xmpp.NS_DELAY in props:
        return

      # Ignore messages from myself
      room = jid.getStripped()
      if ((self.jid==jid) or
          (room in self.get_current_mucs() and jid.getResource()==self.mucs[room]['nick'])):
        return

    # remove nick_name for only_direct or cmd_prefix
    text = self.get_cmd(mess)

    # Run plugin hooks
    self.__run_hooks('msg')
    
    if text is None:
      return

    # Ignore messages from users not seen by this bot
    if (jid not in self.seen) and (jid not in self.real_jids.values()):
      self.log.info('Ignoring message from unseen guest: %s' % jid)
      self.log.debug("I've seen: %s" %
        ["%s" % x for x in self.seen.keys()+self.real_jids.values()])
      return

    # Remember the last-talked-in message thread for replies
    self.__threads[jid] = mess.getThread()
    
    self.log.debug("*** props = %s" % props)
    self.log.debug("*** jid = %s" % jid)
    self.log.debug("*** username = %s" % username)
    self.log.debug("*** type = %s" % typ)
    self.log.debug("*** text = %s" % text)

    if ' ' in text:
      command, args = text.split(' ', 1)
    else:
      command, args = text, ''
    cmd = command.lower()
    self.log.debug("*** cmd = %s" % cmd)

    if cmd in self.hooks['chat']:
        try:
          reply = self.hooks['chat'][cmd](mess, args)
        except Exception, e:
          self.log.exception('An error happened while processing '\
            'a message ("%s") from %s: %s"' %
            (text, jid, traceback.format_exc(e)))
          reply = self.MSG_ERROR_OCCURRED
        if reply:
          self.send_simple_reply(mess, reply, private)
    else:
      # In private chat, it's okay for the bot to always respond.
      # In group chat, the bot should silently ignore commands it
      # doesn't understand or aren't handled by unknown_command().
      self.log.info('Unknown command "%s"' % cmd)
      if typ == 'groupchat':
        default_reply = None
      else:
        default_reply = self.MSG_UNKNOWN_COMMAND % {
          'command': cmd,
          'helpcommand': 'help',
        }
      reply = self.unknown_command(mess, cmd, args)
      if reply is None:
        reply = default_reply
      if reply:
        self.send_simple_reply(mess, reply, private)

################################################################################
# UI Functions                                                                 #
################################################################################

  def unknown_command(self, mess, cmd, args):
    """Default handler for unknown commands

    Override this method in derived class if you
    want to trap some unrecognized commands.  If
    'cmd' is handled, you must return some non-false
    value, else some helpful text will be sent back
    to the sender.
    """
    return None

  def top_of_help_message(self):
    """Returns a string that forms the top of the help message

    Override this method in derived class if you
    want to add additional help text at the
    beginning of the help message.
    """
    return ""

  def bottom_of_help_message(self):
    """Returns a string that forms the bottom of the help message

    Override this method in derived class if you
    want to add additional help text at the end
    of the help message.
    """
    return ""

  @botcmd
  def help(self, mess, args):
    """   Returns a help string listing available options.

    Automatically assigned to the "help" command."""
    if not args:
      if self.__doc__:
        description = self.__doc__.strip()
      else:
        description = 'Available commands:'

      usage = '\n'.join(sorted([
        '%s: %s' % (name, (command.__doc__ or \
          '(undocumented)').strip().split('\n', 1)[0])
        for (name, command) in self.hooks['chat'].iteritems() \
          if name != 'help' \
          and not command._jabberbot_command_hidden
      ]))
      usage = '\n\n' + '\n\n'.join(filter(None,
        [usage, self.MSG_HELP_TAIL % {'helpcommand': 'help'}]))
    else:
      description = ''
      args = self.remove_prefix(args)
      if args in self.hooks['chat']:
        usage = (self.hooks['chat'][args].__doc__ or \
          'undocumented').strip()
      else:
        usage = self.MSG_HELP_UNDEFINED_COMMAND

    top = self.top_of_help_message()
    bottom = self.bottom_of_help_message()
    return ''.join(filter(None, [top, description, usage, bottom]))

################################################################################
# idle_proc: Pinging, MUC join, MUC rejoin                                     #
################################################################################

  def idle_proc(self):
    """This function will be called in the main loop."""
    self._idle_ping()
    self._join_muc()
    self._rejoin_muc()

  def _idle_ping(self):
    """Pings the server, calls on_ping_timeout() on no response.

    Default ping frequency is every 5 minutes.
    """
    if self.__ping_freq and time.time()-self.__lastping>self.__ping_freq:
      self.__lastping = time.time()
      payload = [xmpp.Node('ping',attrs={'xmlns':'urn:xmpp:ping'})]
      ping = xmpp.Protocol('iq',typ='get',payload=payload)
      try:
        res = self.conn.SendAndWaitForResponse(ping,3)
      except IOError as e:
        self.on_ping_timeout()
      if res is None:
        self.on_ping_timeout()

  def on_ping_timeout(self):
    """raises PingTimeout exception"""
    
    raise PingTimeout

  def _join_muc(self):
    """do the actual muc joining if needed"""
    
    if len(self.__muc_pending):
      try:
        (pres,room,user,pword) = self.__muc_pending[0]
        del self.__muc_pending[0]
        self._muc_join(pres,room,user,pword)
        self._muc_join_success(room)
      except MUCJoinFailure as e:
        self._muc_join_failure(room,e.message)
        if room in self.mucs and self.mucs[room]['status'] > self.MUC_OK:
          self.log.debug('Rejoining room "%s" in %i sec' % (room,self.__reconnect_wait))

  def _rejoin_muc(self):
    """attempt to rejoin the MUC if needed"""

    t = time.time()
    if t-self.__reconnect_wait<self.__lastjoin:
      return

    for room in self.mucs:
      if self.mucs[room]['status']>self.MUC_OK:
        self.__lastjoin = time.time()
        muc = self.mucs[room]
        self.muc_join_room(room,muc['nick'],muc['pass'])

################################################################################
# Run and Stop Functions                                                       #
################################################################################

  def quit(self,msg=None):
    """Stop serving messages and exit.

    I find it is handy for development to run the
    jabberbot in a 'while true' loop in the shell, so
    whenever I make a code change to the bot, I send
    the 'reload' command, which I have mapped to call
    self.quit(), and my shell script relaunches the
    new version.
    """
    self.__finished = True
    if msg:
      self.log.debug(msg)

  def shutdown(self):
    """This function will be called when we're done serving

    Override this method in derived class if you
    want to do anything special at shutdown.
    """
    pass

  def _serve_forever(self, connect_callback=None, disconnect_callback=None):
    """Connects to the server and handles messages."""
    conn = self.connect()
    if conn:
      self.log.info('bot connected. serving forever.')
    else:
      self.log.warn('could not connect to server - aborting.')
      return

    if connect_callback:
      connect_callback()
    self.__lastping = time.time()

    while not self.__finished:
      try:
        conn.Process(1)
        self.idle_proc()
      except KeyboardInterrupt:
        self.log.info('bot stopped by user request. '\
          'shutting down.')
        break

    self.shutdown()

    if disconnect_callback:
      disconnect_callback()

  def log_startup_msg(self,rooms=None):
    """log a message to appear when the bot starts"""

    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')
    self.log.critical('JabberBot starting...')
    self.log.info('')
    self.log.info('JID  : %s' % self.jid)
    if rooms:
      for room in rooms:
        self.log.info('Room : %s/%s' % (room['room'],(room['nick'] if room['nick'] else self.get_default_nick())))
    else:
      self.log.info('Room : None')
    self.log.info('Cmds : %i' % len(self.hooks['chat']))
    self.log.info('Log  : %s' % logging.getLevelName(self.log.getEffectiveLevel()))
    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')

  def run_forever(self,
        connect_callback=None, disconnect_callback=None):
    """join a MUCs (optional), server forever, reconnect if needed"""

    self.log_startup_msg(rooms=self.rooms)

    # log unknown exceptions then quit
    try:
      while not self.conn:
        try:
          if len(self.rooms):
            for room in self.rooms:
              self.muc_join_room(room['room'],room['nick'],room['pass'])
          self._serve_forever(connect_callback, disconnect_callback)
        
        # catch known exceptions
        except (PingTimeout,ConnectFailure,SystemShutdown) as e:

          # attempt to reconnect if self.catch_except
          if self.catch_except:
            reason = {PingTimeout:'ping timeout',
                      ConnectFailure:'unable to connect',
                      SystemShutdown:'server shutdown'}
            self.log.error('Connection lost ('+reason[e.__class__]+'); retrying in '+str(self.__reconnect_wait)+' sec')

          # traceback all exceptions and quit if not self.catch_except
          else:
            raise e

          # wait then reconnect
          time.sleep(self.__reconnect_wait)
          self.conn = None
          for room in self.get_current_mucs():
            self.mucs[room]['status'] = self.MUC_PARTED

    # catch all exceptions, add to log, then quit
    except Exception as e:
      self.log.critical('CRITICAL: %s\n\n%s' % (e.__class__.__name__,traceback.format_exc(e)))
      self.shutdown()
