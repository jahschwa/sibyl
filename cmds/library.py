#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2016 Joshua Haas <jahschwa.com>
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

import os,pickle,time,traceback

# def rsamba() imports smbc

from lib.decorators import *
import lib.util as util

@botconf
def conf(bot):
  """add config options"""

  return [{'name' : 'file',
            'default' : 'data/sibyl_lib.pickle',
            'valid' : bot.conf.valid_file},
          {'name' : 'max_matches',
            'default' : 10,
            'parse' : bot.conf.parse_int},
          {'name' : 'audio_dirs',
            'default' : [],
            'valid' : valid_lib,
            'parse' : parse_lib},
          {'name' : 'video_dirs',
            'default' : [],
            'valid' : valid_lib,
            'parse' : parse_lib}]

def valid_lib(conf,lib):
  """return True if the lib contains valid directories or samba shares"""

  for (i,l) in enumerate(lib):
    if isinstance(l,str):
      if not os.path.isdir(l):
        conf.log('warning','path "'+l+'" is not a valid directory')
        return False
    elif isinstance(l,dict):
      if 'server' not in l.keys():
        conf.log('warning','key "server" missing from item '+str(i+1))
        return False
      if 'share' not in l.keys():
        conf.log('warning','key "share" missing from item '+str(i+1))
        return False
  return True

def parse_lib(conf,opt,val):
  """parse the lib into a list"""

  val = val.replace('\n','')

  # paths are separated by semi-colon
  entries = util.split_strip(val,';')
  lib = []
  for entry in entries:
    if entry=='':
      continue
    if ',' in entry:

      if not util.has_module('smbc'):
        conf.log('warning','Ignoring share "%s" (missing smbc)' % entry)
        continue

      # samba share parameters are separated by comma
      params = util.split_strip(entry,',')
      item = {'server':params[0], 'share':params[1],
          'username':None, 'password':None}
      if len(params)>2:
        item['username'] = params[2]
      if len(params)>3:
        item['password'] = params[3]
    else:
      item = entry
    lib.append(item)
  return lib

@botinit
def init(bot):
  """create libraries"""

  bot.add_var('lib_last_rebuilt',time.asctime())
  bot.add_var('lib_last_elapsed',0)
  bot.add_var('lib_audio_dir')
  bot.add_var('lib_audio_file')
  bot.add_var('lib_video_dir')
  bot.add_var('lib_video_file')

  if os.path.isfile(bot.opt('library.file')):
    bot.run_cmd('library',['load'])
  else:
    bot.run_cmd('library',['rebuild'])

  if util.has_module('smbc'):
    import smbc

    # account for older versions of pysmbc that don't specify these
    FILE = 8
    if hasattr(smbc,'FILE'):
      FILE = smbc.FILE
    DIR = 7
    if hasattr(smbc,'DIR'):
      DIR = smbc.DIR

    bot.add_var('smbc_file',FILE)
    bot.add_var('smbc_dir',DIR)

  else:
    bot.log.error("Can't find module smbc; network shares will be disabled")

@botcmd
def library(bot,mess,args):
  """control media library - library (info|load|rebuild|save)"""

  if not args:
    args = ['info']

  # read the library from a pickle and load it into sibyl
  if args[0]=='load':
    start = time.time()
    with open(bot.opt('library.file'),'rb') as f:
      d = pickle.load(f)
    stop = time.time()
    
    bot.lib_last_rebuilt = d['lib_last_rebuilt']
    bot.lib_last_elapsed = d['lib_last_elapsed']
    bot.lib_video_dir = d['lib_video_dir']
    bot.lib_video_file = d['lib_video_file']
    bot.lib_audio_dir = d['lib_audio_dir']
    bot.lib_audio_file = d['lib_audio_file']

    n = len(bot.lib_audio_file)+len(bot.lib_video_file)
    s = ('Library loaded from "%s" with %s files in %f sec' %
        (bot.opt('library.file'),n,stop-start))
    bot.log.info(s)
    return s

  # save sibyl's library to a pickle
  elif args[0]=='save':
    d = ({'lib_last_rebuilt':bot.lib_last_rebuilt,
          'lib_last_elapsed':bot.lib_last_elapsed,
          'lib_video_dir':bot.lib_video_dir,
          'lib_video_file':bot.lib_video_file,
          'lib_audio_dir':bot.lib_audio_dir,
          'lib_audio_file':bot.lib_audio_file})
    with open(bot.opt('library.file'),'wb') as f:
      pickle.dump(d,f,-1)

    s = 'Library saved to "'+bot.opt('library.file')+'"'
    bot.log.info(s)
    return s

  # rebuild the library by traversing all paths then save it
  elif args[0]=='rebuild':

    # when sibyl calls this method on init mess is None
    if mess is not None:
      t = util.sec2str(bot.lib_last_elapsed)
      bot.send('Working... (last rebuild took '+t+')',mess.get_from())

    # time the rebuild and update library vars
    start = time.time()
    bot.lib_last_rebuilt = time.asctime()

    libs = [('lib_video_dir','dir',bot.opt('library.video_dirs')),
            ('lib_video_file','file',bot.opt('library.video_dirs')),
            ('lib_audio_dir','dir',bot.opt('library.audio_dirs')),
            ('lib_audio_file','file',bot.opt('library.audio_dirs'))]
    errors = []
    for lib in libs:
      (r,e) = find(bot,lib[1],lib[2])
      setattr(bot,lib[0],r)
      for x in e:
        if x not in errors:
          bot.log.error(x[1])
          errors.append(x)
    
    bot.lib_last_elapsed = int(time.time()-start)
    result = bot.run_cmd('library',['save'])

    s = bot.run_cmd('library')
    bot.log.info(s)
    if errors:
      s += ' with errors (see log): '+str([x[0] for x in errors])
    return s

  # default prints some info
  t = bot.lib_last_elapsed
  s = str(int(t/60))+':'
  s += str(int(t-60*int(t/60))).zfill(2)
  n = len(bot.lib_audio_file)+len(bot.lib_video_file)
  return 'Rebuilt on '+bot.lib_last_rebuilt+' in '+s+' with '+str(n)+' files'

@botcmd
def search(bot,mess,args):
  """search all paths for matches - search [include -exclude]"""

  if not args:
    args = ['/']
  matches = []

  # search all library paths
  dirs = [bot.lib_video_dir,bot.lib_video_file,
      bot.lib_audio_dir,bot.lib_audio_file]
  for d in dirs:
    matches.extend(util.matches(d,args))

  if len(matches)==0:
    return 'Found 0 matches'

  # reply with matches based on max_matches setting
  if len(matches)>1:
    maxm = bot.opt('library.max_matches')
    if maxm<1 or len(matches)<=maxm:
      return 'Found '+str(len(matches))+' matches: '+util.list2str(matches)
    else:
      return 'Found '+str(len(matches))+' matches'

  return 'Found '+str(len(matches))+' match: '+str(matches[0])

def find(bot,fd,dirs):
  """helper function for library()"""

  paths = []
  smbpaths = []

  # sort paths into local and samba based on whether they're tuples
  for path in dirs:
    if isinstance(path,dict):
      smbpaths.append(path)
    else:
      paths.append(path)

  result = []
  errors = []

  # find all matching directories or files depending on fd parameter
  for path in paths:
    try:
      if fd=='dir':
        contents = util.rlistdir(unicode(path))
      else:
        contents = util.rlistfiles(unicode(path))
      for entry in contents:
        result.append(entry)
    except Exception as e:
      msg = ('Unable to traverse "%s": %s' %
          (path,traceback.format_exc(e).split('\n')[-2]))
      errors.append((path,msg))

  # same as above but for samba shares
  for path in smbpaths:
    try:
      share = 'smb://'+path['server']+'/'+path['share']
      smb = smbc.Context()
      if path['username']:
        smb.functionAuthData = (lambda se,sh,w,u,p:
            (w,path['username'],path['password']))
      
      smb.opendir(share[:share.rfind('/')])
      ignore = [smbc.PermissionError]
      typ = (bot.smbc_dir if fd=='dir' else bot.smbc_file)
      result.extend(rsamba(smb,share,typ,ignore))
    except Exception as e:
      msg = ('Unable to traverse "%s": %s' %
          (share,traceback.format_exc(e).split('\n')[-2]))
      errors.append((share,msg))

  return (result,errors)

# @param ctx (Context) the smbc Context (already authenticated if needed)
# @param path (str) a samba directory
# @param typ (long) the smbc type to return, or all types if None
# @param ignore (list) exceptions to ignore (must derive from Exception)
# @return (list) every item (recursive) in the given directory of type typ
def rsamba(ctx,path,typ=None,ignore=None):
  """recursively list directories"""

  import smbc

  ignore = (ignore or [])
  allitems = []
  d = ctx.opendir(path)
  contents = d.getdents()

  for c in contents:
    cur_path = path+'/'+c.name

    # handle files
    if c.smbc_type==bot.smbc_file:
      if typ in (bot.smbc_file,None):
        allitems.append(cur_path)

    # handle directories
    elif c.smbc_type==bot.smbc_dir and c.name not in ('.','..'):
      if typ in (bot.smbc_dir,None):
        allitems.append(cur_path+'/')
      try:
        allitems.extend(rsamba(ctx,cur_path,typ,ignore))
      except Exception as e:
        ignored = False
        for i in ignore:
          ignored = (ignored or isinstance(e,i))
        if not ignored:
          raise e

    # log unknown types
    else:
      self.log.debug('Unknown smbc_type %s for "%s"' % (c.smbc_type,cur_path))

  return allitems
