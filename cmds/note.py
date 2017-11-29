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

import os,codecs

from sibyl.lib.decorators import *
import sibyl.lib.util as util

import logging
log = logging.getLogger(__name__)

__wants__ = ['xbmc']

@botconf
def conf(bot):
  """add config options"""

  return {'name':'file',
          'default':'data/notes.txt',
          'valid':bot.conf.valid_wfile}

@botinit
def init(bot):
  """initialize note list"""

  if os.path.isfile(bot.opt('note.file')):
    notes = note_parse(bot)
  else:
    with open(bot.opt('note.file'),'w') as f:
      notes = []

  bot.add_var('notes',notes)

@botcmd
def note(bot,mess,args):
  """add a note - note (show|add|playing|remove) [body|num]"""

  # default behavior is "show"
  if not args:
    args = ['show']
  if args[0] not in ['show','add','playing','remove']:
    args.insert(0,'show')

  # set second parameter to make playing/add logic easier
  if len(args)<2:
    args.append('')
  else:
    args[1] = ' '.join(args[1:])

  # add the currently playing file to the body of the note then do "add"
  if args[0]=='playing':

    if not bot.has_plugin('xbmc'):
      return 'This feature not available because plugin "xbmc" not loaded'

    args[0] = 'add'

    active = bot.xbmc_active_player()
    if not active:
      return 'Nothing playing; note not added'
    (pid,typ) = active
    params = {'playerid':pid,'properties':['time']}
    result = bot.xbmc('Player.GetProperties',params)
    t = str(util.time2str(result['result']['time']))

    result = bot.xbmc('Player.GetItem',{'playerid':pid,'properties':['file']})
    fil = os.path.basename(str(result['result']['item']['file']))

    args[1] += ' --- file "'+fil+'" at '+t

  # add the note to bot.notes and bot.note_file
  if args[0]=='add':
    if args[1]=='':
      return 'Note body cannot be blank'
    bot.notes.append(args[1])
    note_write(bot)
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
    note_write(bot)
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
  matches = [i for i in range(0,len(bot.notes))
      if search in bot.notes[i].lower()]

  s = 'Found '+str(len(matches))+' matches: '
  for i in matches:
    s += '(Note #'+str(i+1)+'): '+bot.notes[i]+', '
  return s[:-2]

def note_parse(bot):
  """read the note file into a list"""

  with codecs.open(bot.opt('note.file'),'r',encoding='utf8') as f:
    lines = f.readlines()

  notes = [l.strip() for l in lines if l!='\n']
  log.info('Read '+str(len(notes))+' notes from "'+bot.opt('note.file')+'"')
  return notes

def note_write(bot):
  """write bot.notes to bot.note_file"""

  lines = [l+'\n' for l in bot.notes]
  lines.append('\n')

  with codecs.open(bot.opt('note.file'),'w',encoding='utf8') as f:
    f.writelines(lines)
