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
from lxml.html import fromstring

from decorators import *
from protocol import Message

@botconf
def conf(bot):
  """create the link_echo option"""

  return {'name':'link_echo','default':False,'parse':bot.conf.parse_bool}

@botinit
def init(bot):
  """create the pending_room variable to enable chat responses"""

  bot.pending_room = {}
  bot.pending_tell = []

@botcmd
def all(bot,mess,args):
  """append every user's nick to the front and say it in room"""

  if not len(bot.protocol.get_rooms()):
    return "I'm not in any rooms!"

  if not args:
    return 'You must specify a message'

  # if the room wasn't specified, use the room of the user invoking the command
  frm = mess.get_from()
  room = frm.get_room()

  # if the room is specified and valid, use that
  if len(args)>1:
    if bot.protocol.in_room(args[0]):
      room = args[0]
      args = args[1:]

  if not room:
    return 'Invalid room: "%s"' % args[0]

  bot.protocol.broadcast(' '.join(args),room,frm)

@botcmd
def say(bot,mess,args):
  """if in a room, say this in it - say [room] msg"""

  rooms = bot.protocol.get_rooms()
  if not len(rooms):
    return "I'm not in any rooms!"

  if not args:
    return 'You must specify a room and message'

  # check if the first paramter is a valid room and try to use that
  if args[0] in rooms:
    room = args[0]
    args = args[1:]

  # if they didn't specify a room, but we're only in one, use that
  else:
    if len(rooms)==1:
      room = rooms[0]
    else:
      return 'You must specify a room (I am in more than one)'

  text = ' '.join(args)
  bot.protocol.send(text,room)

@botcmd
def join(bot,mess,args):
  """join a room - [room nick pass]"""

  if not bot.chat_ctrl:
    return 'chat_ctrl disabled'

  # if no room is supplied, just rejoin existing rooms
  if not args:
    bot.run_cmd('rejoin',None)

  # check for optional parameters
  if len(args)<2:
    args.append(bot.nick_name)
  if len(args)<3:
    args.append(None)
  (room,nick,pword) = args

  # add the room to pending_room so we can respond with a message later
  bot.pending_room[room] = mess
  bot.protocol.join_room(room,nick,pword)

@botcmd
def rejoin(bot,mess,args):
  """attempt to rejoin all rooms from the config file"""

  # rejoin every room from the config file if we're not in them
  rejoined = []
  for room in bot.rooms:
    (room,nick,pword) = (room['room'],room['nick'],room['pass'])
    if not bot.protocol.in_room(room):
      rejoined.append(room)
      args = [room,nick]
      if pword:
        args.append(pword)
      bot.run_cmd('join',args,mess)

  if rejoined:
    return 'Attempting to join rooms: '+str(rejoined)
  return 'No rooms to rejoin'

@botcmd
def leave(bot,mess,args):
  """leave the specified room - leave [room]"""

  if not bot.chat_ctrl:
    return 'chat_ctrl disabled'

  # if a room was specified check if it's valid, else use the invoker's room
  rooms = bot.protocol.get_rooms()+[room['room'] for room in bot.rooms]
  room = mess.get_from().get_room()
  if args:
    if args[0] in rooms:
      room = args[0]
    else:
      return 'Unknown room "%s"' % room

  # leave the room or stop trying to reconnect
  in_room = bot.protocol.in_room(room)
  bot.protocol.part_room(room)
  if in_room:
    return 'Left room "%s"' % room
  return 'Reconnecting to room "%s" disabled' % room

@botcmd
def real(bot,mess,args):
  """return the real name of the given nick if known"""

  if not args:
    return 'You must specify a nick'

  room = mess.get_from().get_room()
  if not room:
    return 'This cmd only works in a room'

  # if the full username was specified, get just the nick name
  try:
    nick = bot.protocol.new_user(args[0],Message.GROUP).get_name()
  except:
    nick = args[0]

  # respond with the user's real username if valid and known
  users = [user.get_name() for user in bot.protocol.get_occupants(room)]
  if nick not in users:
    return "I haven't seen nick \"%s\"" % nick
  return bot.protocol.get_real(room,nick).get_base()

@botcmd
def tell(bot,mess,args):
  """give a user a msg when they rejoin - tell [list|remove|nick msg]"""

  # default is to list existing tells
  if not args:
    args = ['list']

  # if invoked from a room, only list tells from that room
  if args[0]=='list':
    if mess.get_type()==Message.GROUP:
      rooms = [mess.get_from().get_room()]
    else:
      rooms = bot.protocol.get_rooms()
    tells = [x for x in bot.pending_tell if x[0] in rooms]
    if tells:
      return str(tells)
    return 'No saved tells'

  elif args[0]=='remove':
    l = len(bot.pending_tell)

    # if no nick specified, remove all tells for the invoker's room
    if len(args)==1:
      room = mess.get_from().get_room()
      bot.pending_tell = [x for x in bot.pending_tell if x[0]!=room]

    # if "*" specified remove all tells
    elif args[1]=='*':
      bot.pending_tell = []

    # if a nick is specified only remove tells for that nick
    else:
      bot.pending_tell = [x for x in bot.pending_tell if x[1]!=args[1]]
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
      bot.protocol.send(x[2],frm)
  bot.pending_tell = new

@botgroup
def link_echo(bot,mess,cmd):
  """get the title of the linked webpage"""

  if cmd is not None:
    return

  if not bot.link_echo:
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
    bot.protocol.send(reply,mess.get_from())

@botmucs
def _muc_join_success(bot,room):
  """notify user of join success"""
  
  _send_muc_result(bot,room,'Success joining room "%s"' % room)

@botmucf
def _muc_join_failure(bot,room,error):
  """notify user of join failure"""
  
  _send_muc_result(bot,room,'Failed to join room "%s" (%s)' % (room,error))

def _send_muc_result(bot,room,msg):
  """helper method for notifying user of result"""
  
  if room not in bot.pending_room:
    return
  mess = bot.pending_room[room]
  del bot.pending_room[room]
  
  bot.protocol.send(msg,mess.get_from())
