#!/usr/bin/env python

import os

from sibyl.jabberbot import botcmd,botfunc,botinit
from sibyl.sibylbot import botconf
from sibyl.util import *

@botconf
def conf(bot):
  """add config options"""

  return [{'name':'note_file',
          'default':'sibyl_note.txt',
          'valid':bot.conf.valid_file}]

@botinit
def init(bot):
  """initialize note list"""
  
  if os.path.isfile(bot.note_file):
    bot.notes = note_parse(bot)
  else:
    with open(bot.note_file,'w') as f:
      bot.notes = []

@botcmd
def note(bot,mess,args):
  """add a note - note (show|add|playing|remove) [body|num]"""

  args = args.split(' ')

  # default behavior is "show"
  if args[0]=='':
    args[0] = 'show'
  if args[0] not in ['show','add','playing','remove']:
    args.insert(0,'show')

  # set second parameter to make playing/add logic easier
  if len(args)<2:
    args.append('')
  else:
    args[1] = ' '.join(args[1:])

  # add the currently playing file to the body of the note then do "add"
  if args[0]=='playing':
    args[0] = 'add'

    pid = bot.xbmc_active_player()
    result = bot.xbmc('Player.GetProperties',{'playerid':pid,'properties':['time']})
    t = str(time2str(result['result']['time']))

    result = bot.xbmc('Player.GetItem',{'playerid':pid,'properties':['file']})
    fil = os.path.basename(str(result['result']['item']['file']))

    args[1] += ' --- file "'+fil+'" at '+t

  # add the note to bot.notes and bot.note_file
  if args[0]=='add':
    if args[1]=='':
      return 'Note body cannot be blank'
    bot.notes.append(args[1])
    bot.note_write()
    return 'Added note #'+str(len(bot.notes))+': '+args[1]

  # remove the specified note number from bot.notes and rewrite bot.note_file
  # notes are stored internally 0-indexed, but users see 1-indexed
  if args[0]=='remove':
    try:
      num = int(args[1])-1
    except ValueError as e:
      return 'Parameter to note remove must be an integer'
    if num<0 or num>len(bot.notes)-1:
      return 'Parameter to note remove must be in [1,'+str(len(bot.notes))+']'

    body = bot.notes[num]
    del bot.notes[num]
    bot.note_write()
    return 'Removed note #'+str(num+1)+': '+body

  # otherwise show notes if they exist
  if len(bot.notes)==0:
    return 'No notes'

  # if args[1] is blank then show all
  if args[1]=='':
    s = ''
    for (i,n) in enumerate(bot.notes):
      s += '(Note #'+str(i+1)+'): '+n+', '
    return s[:-2]

  # if args[1] is a valid integer show that note
  try:
    num = int(args[1])-1
  except ValueError as e:
    num = None

  if num is not None:
    if num<0 or num>len(bot.notes)-1:
      return 'Parameter to note show must be in [1,'+str(len(bot.notes))+']'
    return 'Note #'+str(num+1)+': '+bot.notes[num]

  # if args[1] is text, show matching notes
  search = args[1].lower()
  matches = [i for i in range(0,len(bot.notes)) if search in bot.notes[i].lower()]

  s = 'Found '+str(len(matches))+' matches: '
  for i in matches:
    s += '(Note #'+str(i+1)+'): '+bot.notes[i]+', '
  return s[:-2]

@botfunc
def note_parse(bot):
  """read the note file into a list"""

  with open(bot.note_file,'r') as f:
    lines = f.readlines()

  notes = [l.strip() for l in lines if l!='\n']
  bot.log.info('Read '+str(len(notes))+' notes from "'+bot.note_file+'"')
  return notes

@botfunc
def note_write(bot):
  """write bot.notes to bot.note_file"""

  lines = [l+'\n' for l in bot.notes]
  lines.append('\n')

  with open(bot.note_file,'w') as f:
    f.writelines(lines)
