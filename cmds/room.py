#!/usr/bin/env python

import re

import requests
from lxml.html import fromstring

from decorators import *
from protocol import Message

@botinit
def init(bot):
  """create the room_pending variable to enable chat responses"""

  bot.room_pending = {}

@botcmd
def all(bot,mess,args):
  """append every user's nick to the front and say it in room"""

  if not len(bot.protocol.get_rooms()):
    return "I'm not in any rooms!"

  if not args:
    return 'You must specify a message'

  frm = mess.get_from()
  room = frm.get_room()
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
  if args[0] in rooms:
    room = args[0]
    args = args[1:]
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

  if not args:
    bot.run_cmd('rejoin',None)
  if len(args)<2:
    args.append(bot.nick_name)
  if len(args)<3:
    args.append(None)
  (room,nick,pword) = args

  bot.room_pending[room] = mess
  bot.protocol.join_room(room,nick,pword)

@botcmd
def rejoin(bot,mess,args):
  """attempt to rejoin all rooms from the config file"""

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

  rooms = bot.protocol.get_rooms()+[room['room'] for room in bot.rooms]
  room = mess.get_from().get_room()
  if args:
    if args[0] in rooms:
      room = args[0]
    else:
      return 'Unknown room "%s"' % room

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

  try:
    nick = bot.protocol.new_user(args[0],Message.GROUP).get_name()
  except:
    nick = args[0]

  users = [user.get_name() for user in bot.protocol.get_occupants(room)]
  if nick not in users:
    return "I haven't seen nick \"%s\"" % nick
  return bot.protocol.get_real(room,nick).get_base()

@botmsg
def link_echo(bot,mess,cmd):
  """get the title of the linked webpage"""

  msg = mess.get_text()
  
  try:
    if cmd is None:
      if bot.link_echo:
        if msg is not None and mess.get_type()==Message.GROUP:
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
          bot.protocol.send(reply,mess.get_from())
  except Exception as e:
    bot.log.error('Link echo - '+e.__class__.__name__+' - '+url)

@botmucs
def _muc_join_success(bot,room):
  """override method to notify user of join success"""
  
  _send_muc_result(bot,room,'Success joining room "%s"' % room)

@botmucf
def _muc_join_failure(bot,room,error):
  """override method to notify user of join failure"""
  
  error = bot.MUC_JOIN_ERROR[error]
  _send_muc_result(bot,room,'Failed to join room "%s" (%s)' % (room,error))

def _send_muc_result(bot,room,msg):
  """helper method for notifying user of result"""
  
  if room not in bot.room_pending:
    return
  mess = bot.room_pending[room]
  del bot.room_pending[room]
  
  bot.protocol.send(msg,mess.get_from())
