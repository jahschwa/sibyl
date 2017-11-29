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

import os,sys,pickle,time,traceback,threading,Queue,multiprocessing

# we import smbc in init(), find(), and rsamba() if needed

from sibyl.lib.decorators import *
import sibyl.lib.util as util
from sibyl.lib.password import Password

import logging
log = logging.getLogger(__name__)

@botconf
def conf(bot):
  """add config options"""

  return [
    { 'name'    : 'file',
      'default' : 'data/library.pickle',
      'valid'   : bot.conf.valid_wfile
    },
    { 'name'    : 'max_matches',
      'default' : 10,
      'parse'   : bot.conf.parse_int
    },
    { 'name'    : 'audio_dirs',
      'default' : [],
      'parse'   : parse_lib,
      'valid'   : valid_lib
    },
    { 'name'    : 'video_dirs',
      'default' : [],
      'parse'   : parse_lib,
      'valid'   : valid_lib
    },
    { 'name'    : 'remote',
      'default' : {},
      'parse'   : parse_remote,
      'valid'   : valid_remote
    }
  ]

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
        item['password'] = Password(params[3])
    else:
      item = entry
    lib.append(item)
  return lib

def valid_lib(conf,lib):
  """return True if the lib contains valid directories or samba shares"""

  new = []
  for (i,l) in enumerate(lib):
    if isinstance(l,str):
      if not os.path.isdir(l):
        conf.log('warning','path "'+l+'" is not a valid directory')
        continue
    elif isinstance(l,dict):
      if 'server' not in l.keys():
        conf.log('warning','key "server" missing from item '+str(i+1))
        continue
      if 'share' not in l.keys():
        conf.log('warning','key "share" missing from item '+str(i+1))
        continue
    new.append(l)
  lib[:] = new
  return True

def parse_remote(conf,opt,val):
  """parse the remote replace list into a dict"""

  val = val.replace('\n','')
  entries = util.split_strip(val,';')

  replace = {}
  for entry in entries:
    (local,remote) = util.split_strip(entry,',')
    replace[local] = remote

  return replace

def valid_remote(conf,replace):
  """return True if the local paths are valid"""

  for local in replace.keys():
    if (not os.path.isdir(local)) and (not local.startswith('smb://')):
      conf.log('warning','path "%s" is not a valid directory' % local)
      del replace[local]

  return True

@botinit
def init(bot):
  """create libraries and threading"""

  bot.add_var('lib_last_rebuilt')
  bot.add_var('lib_last_elapsed',0)
  bot.add_var('lib_audio_dir')
  bot.add_var('lib_audio_file')
  bot.add_var('lib_video_dir')
  bot.add_var('lib_video_file')

  bot.add_var('lib_lock',threading.Lock())
  bot.add_var('lib_last_op')
  bot.add_var('lib_pending_send',Queue.Queue())

  if os.path.isfile(bot.opt('library.file')):
    Library(bot,None,['load']).run()
    #bot.run_cmd('library',['load'])
  else:
    Library(bot,None,['rebuild']).run()
    #bot.run_cmd('library',['rebuild'])

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
    log.warning("Can't find module smbc; network shares will be disabled")

  # check for filename unicode support
  enc = sys.getfilesystemencoding()
  if enc!='UTF-8':
    log.warning('Missing unicode support (filesystemencoding=%s)' % enc)
    log.warning('  more details: '
        'https://github.com/TheSchwa/sibyl/wiki/Library'
        '#unicode-considerations')
    bot.error('Unicode file names not supported','library')

# @param path (str) the path to translate
# @return (str) the translated path
@botfunc
def library_translate(bot,path):
  """return the specified library paths, translated if requested"""

  for (local,remote) in bot.opt('library.remote').items():
    if path.startswith(local):
      return path.replace(local,remote,1)

  return path

@botcmd(thread=True)
def library(bot,mess,args):
  """control media library - library (info|load|rebuild|save|reload)"""

  # before botcmd had the threading option, I implemented library as a subclass
  # of threading.Thread and ran it; now that I'm using botcmd(thread=True),
  # I just left all the logic in the Library object but removed the subclassing
  Library(bot,mess,args).run()

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

def find(bot,dirs):
  """helper function for library()"""

  paths = []
  smbpaths = []

  # sort paths into local and samba based on whether they're tuples
  for path in dirs:
    if isinstance(path,dict):
      smbpaths.append(path)
    else:
      paths.append(path)

  dirs = []
  files = []
  errors = []

  # find all matching directories or files depending on fd parameter
  for path in paths:
    try:
      (temp_dirs,temp_files) = util.rlistdir(unicode(path))
      dirs.extend(temp_dirs)
      files.extend(temp_files)
    except Exception as e:
      msg = ('Unable to traverse "%s": %s' %
          (path,traceback.format_exc(e).split('\n')[-2]))
      errors.append((path,msg))

  if smbpaths:
    import smbc

  # same as above but for samba shares
  for path in smbpaths:
    temp_dirs = []
    temp_files = []

    try:
      share = 'smb://'+path['server']+'/'+path['share']
      smb = smbc.Context()
      if path['username']:
        pword = path['password'] and path['password'].get()
        smb.functionAuthData = (lambda se,sh,w,u,p:
            (w,path['username'],pword))

      smb.opendir(share[:share.rfind('/')])
      ignore = [smbc.PermissionError]

      # even though we're just doing blocking I/O, threading isn't enough
      # we need sub-processes via multiprocessing for samba shares
      # because pysmbc doesn't release the GIL so it still blocks in threads
      log.debug('Starting new process for "%s"' % share)
      q = multiprocessing.Queue()
      e = multiprocessing.Queue()
      args = (bot.smbc_dir,bot.smbc_file,q,e,smb,share,ignore)
      p = multiprocessing.Process(target=rsamba,args=args)
      p.start()

      # we're using a Queue for message passing
      while p.is_alive() or not q.empty():
        while not q.empty():
          (typ,name) = q.get()
          if typ==bot.smbc_dir:
            temp_dirs.append(unicode(name))
          elif typ==bot.smbc_file:
            temp_files.append(unicode(name))
        time.sleep(0.1)

      # the child process also reports errors using a Queue
      log.debug('Process done with%s errors' % ('out' if e.empty() else ''))
      if e.empty():
        dirs.extend(temp_dirs)
        files.extend(temp_files)
      else:
        raise e.get()

    except Exception as ex:
      msg = ('Unable to traverse "%s": %s' %
          (share,traceback.format_exc(ex).split('\n')[-2]))
      errors.append((share,msg))

  return (dirs,files,errors)

# @param smbc_dir (int) the smbc directory enum
# @param smbc_file (int) the smbc file enum
# @param q (Queue) the queue to add entries
# @param e (Queue) the queue to add errors
# @param ctx (Context) the smbc Context (already authenticated if needed)
# @param path (str) a samba directory
# @param typ (long) the smbc type to return, or all types if None
# @param ignore (list) exceptions to ignore (must derive from Exception)
# @return tuple(list,list) all (dirs,files) in the given path (recursive)
def rsamba(smbc_dir,smbc_file,q,e,ctx,path,ignore=None):
  """recursively list directories"""

  import smbc

  ignore = (ignore or [])
  allitems = []
  if isinstance(path,unicode):
    path.encode('utf8')
  d = ctx.opendir(path)
  contents = d.getdents()

  for c in contents:
    cur_path = path+'/'+c.name.encode('utf8')

    # handle files
    if c.smbc_type==smbc_file:
      q.put((smbc_file,cur_path.decode('utf8')))

    # handle directories
    elif c.smbc_type==smbc_dir:
      if c.name in ('.','..'):
        continue
      q.put((smbc_dir,(cur_path+'/').decode('utf8')))
      try:
        if not rsamba(smbc_dir,smbc_file,q,e,ctx,cur_path,ignore):
          return False
      except Exception as ex:
        ignored = False
        for i in ignore:
          ignored = (ignored or isinstance(ex,i))
        if not ignored:
          e.put(ex)
          return False

  return True

################################################################################
# LibraryThread class
################################################################################

class Library(object):

  def __init__(self,bot,mess,args):

    self.bot = bot
    self.mess = mess
    self.args = args
    self.lock = bot.lib_lock

  def run(self):

    # if a "rebuild" is executing return immediately, else wait for the lock
    if not self.lock.acquire(False):
      if self.bot.lib_last_op=='rebuild':
        t = util.sec2str(time.time()-self.bot.lib_last_rebuilt)
        self.send('Library locked for rebuild'+
            ' (last took %s, current at %s)'
            % (util.sec2str(self.bot.lib_last_elapsed),t))
        return
      else:
        log.debug('Waiting for other thread to release library lock')
        self.lock.acquire(True)

    try:

      if self.args:
        if self.args[0] not in ('load','save','rebuild','info','reload'):
          self.send('Unknown option "%s"' % self.args[0])
          return
      else:
        self.args = ['info']

      self.bot.lib_last_op = self.args[0]
      msg = getattr(self,self.args[0])()
      self.send(msg)

    except Exception as ex:

      log.error('Error in thread while executing "%s"' % self.args[0])
      full = traceback.format_exc(ex)
      short = full.split('\n')[-2]

      log.error('  %s' % short)
      log.debug(full)

    finally:

      self.lock.release()

  def send(self,text):
    """queue a message to be sent"""

    # when called during bot init mess is None so don't send anything
    if self.mess:
      self.bot.send(text,self.mess.get_from())

  def load(self):
    """read the library from a pickle and load it into sibyl"""

    start = time.time()
    with open(self.bot.opt('library.file'),'rb') as f:
      d = pickle.load(f)
    stop = time.time()

    names = ['lib_last_rebuilt','lib_last_elapsed',
        'lib_video_dir','lib_video_file','lib_audio_dir','lib_audio_file']
    for name in names:
      setattr(self.bot,name,d[name])

    n = len(self.bot.lib_audio_file)+len(self.bot.lib_video_file)
    s = ('Library loaded from "%s" with %s files in %f sec' %
        (self.bot.opt('library.file'),n,stop-start))
    log.info(s)

    return s

  def save(self):
    """save sibyl's library to a pickle"""

    names = ['lib_last_rebuilt','lib_last_elapsed',
        'lib_video_dir','lib_video_file','lib_audio_dir','lib_audio_file']
    d = {name:getattr(self.bot,name) for name in names}

    with open(self.bot.opt('library.file'),'wb') as f:
      pickle.dump(d,f,-1)

    s = 'Library saved to "%s"' % self.bot.opt('library.file')
    log.info(s)

    return s

  def rebuild(self):
    """rebuild the library by traversing all paths then save it"""

    t = util.sec2str(self.bot.lib_last_elapsed)
    self.send('Working... (last rebuild took %s)' % t)

    # time the rebuild and update library vars
    start = time.time()
    self.bot.lib_last_rebuilt = time.time()

    # update library vars and log errors
    errors = []
    for lib in ('audio','video'):
      (dirs,files,errs) = find(self.bot,self.bot.opt('library.%s_dirs' % lib))
      setattr(self.bot,'lib_%s_dir' % lib,dirs)
      setattr(self.bot,'lib_%s_file' % lib,files)
      for e in errs:
        if e not in errors:
          log.error(e[1])
          errors.append(e)

    self.bot.lib_last_elapsed = int(time.time()-start)
    result = self.save()

    s = self.info()
    log.info(s)
    if errors:
      s += ' with errors (see log): '+str([x[0] for x in errors])

    return s

  def info(self):
    """give some info"""

    t = self.bot.lib_last_elapsed
    s = str(int(t/60))+':'
    s += str(int(t-60*int(t/60))).zfill(2)
    n = len(self.bot.lib_audio_file)+len(self.bot.lib_video_file)
    t = time.asctime(time.localtime(self.bot.lib_last_rebuilt))

    return 'Rebuilt on %s in %s with %s files' % (t,s,n)

  def reload(self):
    """reload search paths from the config file"""

    if not self.bot.has_plugin('general'):
      return 'Operation not available because plugin "general" not loaded'

    for opt in ('video','audio'):
      result = self.bot.run_cmd('config',['reload','library.%s_dirs' % opt])
      self.send(result)

    return 'NOTE: run "library rebuild" to index new directories'
