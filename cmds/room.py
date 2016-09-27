#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2016 Joshua Haas <jahschwa.com>
# Copyright (c) 2016 Jonathan Frederickson <terracrypt.net>
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

import re,time

import requests

from lib.decorators import *
from lib.protocol import Message,Room
import lib.util as util

@botconf
def conf(bot):
  """create the link_echo option"""

  return {
    'name':'link_echo',
    'default':False,
    'parse':bot.conf.parse_bool,
    'valid':valid
  }

def valid(conf,echo):
  """check for lxml"""
  
  if (not echo) or util.has_module('lxml'):
    return True
  
  conf.log('error',"Can't find module lxml; link_echo will be disabled")
  return False

@botinit
def init(bot):
  """create the pending_room variable to enable chat responses"""

  bot.add_var('pending_room',{})
  bot.add_var('pending_tell',[])
  
  if not util.has_module('lxml'):
    bot.log.debug("Can't find module lxml; unregistering link_echo hook")
    del bot.hooks['group']['room.link_echo']

@botcmd
def all(bot,mess,args):
  """append every user's nick to the front and say it in room"""

  proto = bot.get_protocol(mess)
  if not len(proto.get_rooms()):
    return "I'm not in any rooms!"

  if not args:
    return 'You must specify a message'

  # if the room wasn't specified, use the room of the user invoking the command
  frm = mess.get_from()
  room = frm.get_room()

  # if the room is specified and valid, use that
  if len(args)>1:
    if proto.in_room(Room(args[0])):
      room = Room(args[0])
      args = args[1:]

  if not room:
    return 'Invalid room: "%s"' % args[0]

  proto.broadcast(' '.join(args),room,frm)

@botcmd
def say(bot,mess,args):
  """if in a room, say this in it - say [room] msg"""

  proto = bot.get_protocol(mess)
  rooms = proto.get_rooms()
  if not len(rooms):
    return "I'm not in any rooms!"

  if not args:
    return 'You must specify a room and message'

  # check if the first paramter is a valid room and try to use that
  if args[0] in [r.get_name() for r in rooms]:
    room = Room(args[0])
    args = args[1:]

  # if they didn't specify a room, but we're only in one, use that
  else:
    if len(rooms)==1:
      room = rooms[0]
    else:
      return 'You must specify a room (I am in more than one)'

  text = ' '.join(args)
  proto.send(text,room)

@botcmd(ctrl=True)
def join(bot,mess,args):
  """join a room - [room nick pass]"""

  # if no room is supplied, just rejoin existing rooms
  if not args:
    return bot.run_cmd('rejoin',None)

  name = args[0]
  nick = bot.opt('nick_name')
  pword = None

  # check for optional parameters
  if len(args)>1:
    nick = args[1]
  if len(args)>2:
    pword = args[2]
  room = Room(name,nick,pword,mess.get_protocol())

  # add the room to pending_room so we can respond with a message later
  bot.pending_room[room] = mess
  bot.get_protocol(mess).join_room(room)

@botcmd
def rejoin(bot,mess,args):
  """attempt to rejoin all rooms from the config file"""

  pname = mess.get_protocol()
  proto = bot.get_protocol(mess)

  # rejoin every room from the config file if we're not in them
  rejoined = []
  for room in bot.opt('rooms').get(pname,[]):
    room = Room(room['room'],room['nick'],room['pass'])
    if not proto.in_room(room):
      rejoined.append(room.get_name())
      proto.join_room(room)

  if rejoined:
    return 'Attempting to join rooms: '+str(rejoined)
  return 'No rooms to rejoin'

@botcmd(ctrl=True)
def leave(bot,mess,args):
  """leave the specified room - leave [room]"""

  pname = mess.get_protocol()
  proto = bot.get_protocol(mess)

  # if a room was specified check if it's valid, else use the invoker's room
  rooms = [Room(room['room']) for room in bot.opt('rooms').get(pname,[])]
  rooms = proto.get_rooms()+rooms
  room = mess.get_from().get_room()
  if args:
    if args[0] in [room.get_name() for room in rooms]:
      room = Room(args[0])
    else:
      return 'Unknown room "%s"' % room

  if not room:
    return 'You must specify a room'

  # leave the room or stop trying to reconnect
  in_room = proto.in_room(room)
  proto.part_room(room)
  if in_room:
    return 'Left room "%s"' % room
  return 'Reconnecting to room "%s" disabled' % room

@botcmd
def real(bot,mess,args):
  """return the real name of the given nick if known"""

  proto = bot.get_protocol(mess)

  if not args:
    return 'You must specify a nick'

  room = mess.get_from().get_room()
  if not room:
    return 'This cmd only works in a room'
  nick = args[0]

  # respond with the user's real username if valid and known
  users = [user.get_name() for user in proto.get_occupants(room)]
  if nick not in users:
    return "I haven't seen nick \"%s\"" % nick
  return proto.get_real(room,nick).get_base()

@botcmd
def tell(bot,mess,args):
  """give a user a msg when they rejoin - tell [list|remove|nick msg]"""

  proto = bot.get_protocol(mess)

  # default is to list existing tells
  if not args:
    args = ['list']

  # if invoked from a room, only list tells from that room
  if args[0]=='list':
    if mess.get_type()==Message.GROUP:
      rooms = [mess.get_from().get_room()]
    else:
      rooms = proto.get_rooms()
    tells = [x for x in bot.pending_tell if x[0] in rooms]
    if tells:
      return str([(t[0].get_name(),t[1],t[2]) for t in tells])
    return 'No saved tells'

  elif args[0]=='remove':
    if not mess.get_type()==Message.GROUP:
      return 'You can only remove tells in a room'
    l = len(bot.pending_tell)

    # if no nick specified, remove all tells for the invoker's room
    if len(args)==1:
      room = mess.get_from().get_room()
      bot.pending_tell = [x for x in bot.pending_tell if x[0]!=room]

    # if "*" specified remove all tells for that protocol
    elif args[1]=='*':
      bot.pending_tell = [x for x in bot.pending_tell
          if x[0].get_protocol()!=mess.get_protocol()]

    # if a nick is specified only remove tells for that nick
    else:
      bot.pending_tell = [x for x in bot.pending_tell
          if x[0]!=mess.get_from.get_room() or x[1]!=args[1]]
    return 'Removed %s tells' % (l-len(bot.pending_tell))

  if mess.get_type()!=Message.GROUP:
    return 'You can only use this cmd in a room'

  if len(args)<2:
    return 'You must specify a nick and a message'

  # compose a meaningful response for the specified user
  frm = mess.get_from()
  room = frm.get_room()
  to = args[0]
  frm = frm.get_name()
  msg = ' '.join(args[1:])
  t = time.asctime()

  # add it to pending_tell to act on when status changes
  msg = '%s: %s said "%s" at %s' % (to,frm,msg,t)
  bot.pending_tell.append((room,to,msg))
  return 'Added tell for "%s"' % to

@botstatus
def tell_cb(bot,mess):
  """check if we have a pending "tell" for the user"""

  frm = mess.get_from()
  room = frm.get_room()

  # we only care about status messages from rooms
  if not room:
    return

  # we only care about status messages for users entering the room
  (status,msg) = mess.get_status()
  if status<=Message.OFFLINE:
    return

  # check for tells matching the room and nick from the status and act on them
  name = frm.get_name()
  new = []
  for x in bot.pending_tell:
    if x[0]!=room or x[1]!=name:
      new.append(x)
    else:
      bot.send(x[2],frm)
  bot.pending_tell = new

@botgroup
def link_echo(bot,mess,cmd):
  """get the title of the linked webpage"""

  if not bot.opt('room.link_echo'):
    return

  try:
    from lxml.html import fromstring
  except ImportError:
    bot.log.error("Can't import lxml; disabling link_echo")
    bot.conf.opts['room.link_echo'] = False

  if cmd is not None:
    return

  msg = mess.get_text()
  try:
    titles = []
    urls = re.findall(r'(https?://[^\s]+)', msg)
    if len(urls)==0:
      return
    for url in urls:
      r = requests.get(url)
      title = fromstring(r.content).findtext('.//title')
      titles.append(title.strip())
    linkcount = 1
    reply = ""
    for title in titles:
      if title is not None:
        reply += "[" + str(linkcount)+ "] " + title + " "
        linkcount += 1
  except Exception as e:
    bot.log.error('Link echo - '+e.__class__.__name__+' - '+url)
  else:
    bot.send(reply,mess.get_from())

@botrooms
def _muc_join_success(bot,room):
  """notify user of join success"""
  
  _send_muc_result(bot,room,'Success joining room "%s"' % room)

@botroomf
def _muc_join_failure(bot,room,error):
  """notify user of join failure"""
  
  _send_muc_result(bot,room,'Failed to join room "%s" (%s)' % (room,error))

def _send_muc_result(bot,room,msg):
  """helper method for notifying user of result"""

  if room not in bot.pending_room:
    return
  mess = bot.pending_room[room]
  del bot.pending_room[room]
  
  bot.send(msg,mess.get_from())
