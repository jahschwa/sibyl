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

import os,time,codecs

from sibyl.lib.decorators import *
import sibyl.lib.util as util

import logging
log = logging.getLogger(__name__)

__depends__ = ['xbmc','library']

@botconf
def conf(bot):
  """add config options"""

  return [{'name':'file',
          'default':'data/bookmarks.txt',
          'valid':bot.conf.valid_wfile},
          {'name':'resume_next',
          'default':False,
          'parse':bot.conf.parse_bool}]

@botinit
def init(bot):
  """initialize bookmark dict and last played str for bookmarking"""

  if os.path.isfile(bot.opt('bookmark.file')):
    bm_store = bm_parse(bot)
  else:
    with open(bot.opt('bookmark.file'),'w') as f:
      bm_store = {}

  bot.add_var('bm_store',bm_store)
  bot.add_var('last_resume',persist=True)
  # note the "last_played" var is created in xbmc.py so don't do it here

@botcmd
def bookmark(bot,mess,args):
  """manage bookmarks - bookmark [show|set|remove|update] [name]"""

  if not args:
    args = ['show']

  if args[0]=='set':
    # check if last_played is set
    if bot.last_played is None:
      return 'No active audios or videos playlist to bookmark'

    # check if anything is actually playing
    if bot.xbmc_active_player() is None:
      return 'Nothing playing'

    # check if a name was passed
    name = bot.last_played[1]
    args = args[1:]
    if len(args)>0:
      name = str(args[0])

    # get info for bookmark
    pid = bot.last_played[0]
    path = bot.last_played[1]
    params = {'playerid':pid,'properties':['position','time']}
    result = bot.xbmc('Player.GetProperties',params)
    pos = result['result']['position']
    t = str(util.time2str(result['result']['time']))
    add = time.time()
    result = bot.xbmc('Player.GetItem',{'playerid':pid,'properties':['file']})
    fil = os.path.basename(str(result['result']['item']['file']))

    # note that the position is stored 0-indexed
    bot.bm_store[name] = {'path':path,'add':add,'time':t,
                          'pid':pid,'pos':pos,'file':fil}
    bm_update(bot,name,bot.bm_store[name])
    return 'Bookmark added for "'+name+'" item '+str(pos+1)+' at '+t

  elif args[0]=='remove':
    if len(args)==1:
      return 'To remove all bookmarks use "bookmarks remove *"'
    if not bm_remove(bot,args[1]):
      return 'Bookmark "'+name+'" not found'
    return 'Removed bookmark "%s"' % args[1]

  elif args[0]=='update':
    if not bot.last_resume:
      return 'No active bookmark'
    return bot.run_cmd('bookmark',['set',bot.last_resume])

  elif args[0]=='show':
    args = args[1:]

  # actual code for show function because this is default behavior
  if len(bot.bm_store)==0:
    return 'No bookmarks'

  # if no args are passed return all bookmark names
  matches = bot.bm_store.keys()
  if len(args)==0 or args[0]=='':
    return 'There are '+str(len(matches))+' bookmarks: '+', '.join(matches)

  # if a search term was passed find matches and display them
  search = ' '.join(args).lower()
  matches = [m for m in matches if search in m.lower()]

  entries = []
  for m in matches:
    item = bot.bm_store[m]
    pos = item['pos']
    t = item['time']
    f = item['file']
    entries.append('"%s" at item %s and time %s which is "%s"' % (m,pos+1,t,f))
  if len(entries)==0:
    return 'Found 0 bookmarks'
  if len(entries)==1:
    return 'Found 1 bookmark: '+str(entries[0])
  return 'Found '+str(len(entries))+' bookmarks: '+util.list2str(entries)

@botcmd
def resume(bot,mess,args):
  """resume playing a playlist - resume [name] [next]"""

  if not args:
    args = ['']

  # if there are no bookmarks return
  if len(bot.bm_store)==0:
    return 'No bookmarks'

  # check for "next" as last arg
  start_next = (args[-1]=='next')
  start_current = (args[-1]=='current')

  if start_next or start_current:
    args = args[:-1]

  start_next |= (bot.opt('bookmark.resume_next') and not start_current)

  # check if a name was passed
  name = bm_recent(bot)
  if args and args[0]:
    name = ' '.join(args)

  # get info from bookmark
  if name not in bot.bm_store.keys():
    return 'No bookmark named "'+name+'"'
  item = bot.bm_store[name]
  path = item['path']
  pid = item['pid']
  pos = item['pos']
  t = item['time']

  # open the directory as a playlist
  if start_next:
    pos += 1

  # note that the user-facing functions assume 1-indexing
  args = [path,'#'+str(pos+1)]

  if pid==0:
    result = bot.run_cmd('audios',args)
  elif pid==1:
    result = bot.run_cmd('videos',args)
  else:
    return 'Error in bookmark for "'+name+'": invalid pid'+pid

  if not start_next and util.str2sec(t)>10:
    bot.run_cmd('seek',[t])
    result += ' at '+t

  bot.last_resume = name
  return result

def bm_parse(bot):
  """read the bm_file into a dict"""

  d = {}
  with codecs.open(bot.opt('bookmark.file'),'r',encoding='utf8') as f:
    lines = [l.strip() for l in f.readlines() if l.strip()]

  # tab-separated each line is: name path pid position file time added
  for l in lines:
    (name,props) = bm_unformat(l)
    d[name] = props

  fname = bot.opt('bookmark.file')
  log.info('Parsed %s bookmarks from "%s"' % (len(d),fname))
  return d

def bm_update(bot,name,props):
  """add or modify the entry for name with props in dict and file
  returns True if name was modified or False if name was added"""

  result = bm_remove(bot,name)
  bm_add(bot,name,props)
  return result

def bm_add(bot,name,props):
  """add the entry for name with props to dict and file. Note
  that this function could add duplicates without proper checking"""

  bot.bm_store[name] = props

  # the bookmark file should always end in a newline
  with codecs.open(bot.opt('bookmark.file'),'a',encoding='utf8') as f:
    f.write(bm_format(name,props)+'\n')

def bm_remove(bot,name):
  """remove the entry for name from dict and file if it exists
  returns False if name was not found or True if name was removed"""

  # passing "*" removes all bookmarks
  if name=='*':
    bot.bm_store = {}
    with codecs.open(bot.opt('bookmark.file'),'w',encoding='utf8') as f:
      f.write('')
    return True

  # return False if name does not exist
  if name not in bot.bm_store.keys():
    return False

  del bot.bm_store[name]

  with codecs.open(bot.opt('bookmark.file'),'r',encoding='utf8') as f:
    lines = f.readlines()

  lines = [l for l in lines if l.split('\t')[0]!=name]

  with codecs.open(bot.opt('bookmark.file'),'w',encoding='utf8') as f:
    f.writelines(lines)

  # return True if name was removed
  return True

def bm_format(name,props):
  """return props as a string formatted for the bm_file"""

  order = ['path','pid','pos','file','time','add']
  for prop in order:
    name += ('\t'+unicode(props[prop]))
  return name

def bm_unformat(line):
  """return the name and props from the line as a tuple"""

  line = line.strip()
  (name,path,pid,pos,fil,t,add) = line.split('\t')
  pid = int(pid)
  pos = int(pos)
  add = float(add)
  props = {'path':path,'add':add,'time':t,'pid':pid,'pos':pos,'file':fil}

  # name is str, props is dict
  return (name,props)

def bm_recent(bot):
  """return the most recent bookmark from the dict"""

  name = None
  add = 0
  for k in bot.bm_store.keys():
    t = bot.bm_store[k]['add']
    if t > add:
      name = k
      add = t

  return name
