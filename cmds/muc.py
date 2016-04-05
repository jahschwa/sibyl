#!/usr/bin/env python

import re

import requests
from lxml.html import fromstring

from sibyl.jabberbot import botcmd,botfunc,botinit,botmucs,botmucf,botmsg

@botcmd
def all(bot,mess,args):
  """append every user's nick to the front and say it in MUC"""

  if not len(bot.get_current_mucs()):
    return "I'm not in any rooms!"

  room = bot.last_muc
  frm = mess.getFrom()
  cmd = args.split(' ')
  if cmd[0] in bot.get_current_mucs():
    room = cmd[0]
    args = ' '.join(cmd[1:])
  elif frm.getStripped() in bot.get_current_mucs():
    room = frm.getStripped()

  s = room+' '
  for jid in bot.seen:
    if ((room==jid.getStripped())
        and (bot.mucs[room]['nick']!=jid.getResource())
        and (jid!=frm)):
      s += (jid.getResource()+': ')

  if room==frm.getStripped():
    frm = frm.getResource()
  else:
    frm = str(frm)

  bot.say(None,s+'[ '+args+' ] '+frm)

@botcmd
@botfunc
def say(bot,mess,args):
  """if in a MUC, say this in it"""

  if not len(bot.get_current_mucs()):
    return "I'm not in any rooms!"

  room = bot.last_muc
  cmd = args.split(' ')
  if cmd[0] in bot.get_current_mucs():
    room = cmd[0]
    args = ' '.join(cmd[1:])

  msg = bot.build_message(args)
  msg.setTo(room)
  msg.setType('groupchat')
  bot.send_message(msg)

@botcmd
@botfunc
def join(bot,mess,args):
  """join a MUC - [roomJID nick pass]"""

  if not bot.chat_ctrl:
    return 'chat_ctrl disabled'

  if args=='':
    bot.rejoin(None,None)
  args = args.split(' ')
  if len(args)<2:
    args.append(bot.nick_name)
  if len(args)<3:
    args.append(None)
  (room,nick,pword) = args

  bot.muc_pending[room] = mess
  bot.muc_join_room(room,nick,pword)

@botcmd
def rejoin(bot,mess,args):
  """rejoin the last used MUC"""

  if not len(bot.get_inactive_mucs()):
    return 'No room to rejoin; use the "join" command instead'
  room = bot.last_muc
  if bot.mucs[room]['status']==bot.MUC_OK:
    return 'I am already in "%s"!' % room
  args = room+' '+bot.mucs[room]['nick']
  if bot.mucs[room]['pass'] is not None:
    args += (' '+bot.mucs[room]['pass'])

  return bot.join(mess,args)

@botcmd
def leave(bot,mess,args):
  """leave the specified MUC - leave [room]"""

  if not len(bot.get_active_mucs()):
    return 'I am not in any rooms!'

  room = bot.last_muc
  frm = mess.getFrom()
  cmd = args.split(' ')
  if len(cmd)>0 and cmd[0].strip():
    if cmd[0] in bot.get_active_mucs():
      room = cmd[0]
      args = ' '.join(cmd[1:])
    else:
      return 'Unknown room "%s"' % cmd[0]
  elif frm.getStripped() in bot.get_current_mucs():
    room = frm.getStripped()

  status = bot.mucs[room]['status']
  bot.muc_part_room(room,username=bot.mucs[room]['nick'])
  if status==bot.MUC_OK:
    return 'Left room "%s"' % room
  return 'Stopped reconnecting to room "%s" (%s)' % (room,bot.MUC_CODES[status][0])

@botcmd
def realjid(bot,mess,args):
  """return the real JID of the given MUC nick if known"""

  if '@' not in args:
    args = mess.getFrom().getStripped()+'/'+args
  if args.lower() in [str(jid).lower() for jid in bot.seen]:
    return str(bot.real_jids.get(args,args))
  return "I haven't seen that nick"

@botmsg
def link_echo(bot,mess,cmd):
  """get the title of the linked webpage"""

  msg = mess.getBody()
  
  try:
    if cmd is None:
      if bot.link_echo:
        if msg is not None and mess.getType()=='groupchat':
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
          bot.send_simple_reply(mess, reply)
  except Exception as e:
    bot.log.error('Link echo - '+e.__class__.__name__+' - '+url)

@botmucs
def _muc_join_success(bot,room):
  """override method to notify user of join success"""
  
  bot._send_muc_result(room,'Success joining room "%s"' % room)

@botmucf
def _muc_join_failure(bot,room,error):
  """override method to notify user of join failure"""
  
  error = bot.MUC_JOIN_ERROR[error]
  bot._send_muc_result(room,'Failed to join room "%s" (%s)' % (room,error))

@botfunc
def _send_muc_result(bot,room,msg):
  """helper method for notifying user of result"""
  
  if room not in bot.muc_pending:
    return
  mess = bot.muc_pending[room]
  del bot.muc_pending[room]
  
  bot.send_simple_reply(mess,msg)
