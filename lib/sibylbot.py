#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2017 Joshua Haas <jahschwa.com>
#
# JabberBot: A simple jabber/xmpp bot framework
# Copyright (c) 2007-2012 Thomas Perl <thp.io/about>
# $Id: d1c7090edd754ff0da8ef4eb10d4b46883f34b9f $
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
#
# Sections:
#
# AAA - SibylBot
# BBB - Plug-in framework
# CCC - Callbacks for Protocols
# DDD - Helper functions
# EEE - Chat commands
# FFF - UI Functions
# GGG - Run and Stop Functions
# HHH - User-facing functions
#
################################################################################

import sys,logging,re,os,imp,inspect,traceback,time,pickle,Queue,collections

from sibyl.lib.config import Config
from sibyl.lib.protocol import Message,Room,User
from sibyl.lib.protocol import (ProtocolError,PingTimeout,ConnectFailure,
    AuthFailure,ServerShutdown)
from sibyl.lib.decorators import botcmd,botrooms,botcon
import sibyl.lib.util as util
from sibyl.lib.thread import SmartThread

__author__ = 'Joshua Haas <haas.josh.a@gmail.com>'
__version__ = 'v6.0.0'
__website__ = 'https://github.com/TheSchwa/sibyl'
__license__ = 'GNU General Public License version 3 or later'

class DuplicateVarError(Exception):
  pass

class SigTermInterrupt(Exception):
  pass

################################################################################
# AAA - SibylBot
################################################################################

class SibylBot(object):
  """More details: https://github.com/TheSchwa/sibyl/wiki/Commands"""

  # UI-messages (overwrite to change content)
  MSG_UNKNOWN_COMMAND = 'Unknown command: "%(command)s". '\
    'Type "%(helpcommand)s" for available commands.'
  MSG_HELP_TAIL = 'Type %(helpcommand)s <command name> to get more info '\
    'about that specific command.'
  MSG_HELP_UNDEFINED_COMMAND = 'That command is not defined.'
  MSG_ERROR_OCCURRED = 'Sorry for your inconvenience. '\
    'An unexpected error occurred.'
  MSG_UNHANDLED = 'Please consider reporting the above error to the developers.'

  # Bot state
  INIT = 0
  READY = 1
  RUNNING = 2
  EXITED = 3

  def __init__(self,conf_file='sibyl.conf'):
    """create a new sibyl instance, load: conf, protocol, plugins"""

    self.__stats = {'born':time.time(),'cmds':0,'ex':0,'forbid':0,'discon':0}
    self.__status = SibylBot.INIT

    # keep track of errors for use with "errors" command
    self.errors = []

    # create "namespace" dicts to keep track of who added what for error msgs
    self.ns_opt = {}
    self.ns_func = {}
    self.ns_cmd = {}

    # load config to get cmd_dir and protocols
    self.conf_file = conf_file
    (result,dup_plugins,duplicates) = self.__init_config()

    # configure logging
    mode = 'a' if self.opt('log_append') else 'w'
    logging.basicConfig(filename=self.opt('log_file'),filemode=mode,
        format='%(asctime).19s | %(name)-8.8s | %(levelname).3s | %(message)s',
        level=self.opt('log_level'))
    self.log = logging.getLogger('sibylbot')
    if not self.opt('log_requests'):
      logging.getLogger("requests").setLevel(logging.CRITICAL+10)
    if not self.opt('log_urllib3'):
      logging.getLogger("urllib3").setLevel(logging.CRITICAL+10)
    self.__log_startup_msg()

    # log config errors and check for success
    self.errors.extend(['(startup.config) '+x[1] for x in self.conf.log_msgs])
    self.conf.process_log()
    self.conf.real_time = True
    if dup_plugins:
      self.log.error(dup_plugins)
      self.log.critical('Duplicate plugin names; exiting')
    elif result==Config.FAIL or duplicates:
      self.log.critical('Error parsing config file; exiting')
    elif result==Config.ERRORS:
      self.log.warning('Parsed config file with warnings')

    # if we are missing required config options exit with status message
    if dup_plugins:
      self.__fatal('duplicate plugins')
    elif result==Config.FAIL or duplicates:
      self.__fatal('unusuable config')

    self.log.info('Success parsing config file')
    self.log.info('')

    # initialise variables
    self.__finished = False
    self.__reboot = False
    self.__recons = {}
    self.__tell_rooms = []
    self.__pending_send = Queue.Queue()
    self.__deferred = []
    self.__deferred_count = {}
    self.__pending_del = Queue.Queue()
    self.__last_idle = 0
    self.__idle_count = {}
    self.__idle_last = {}
    self.last_cmd = {}

    # load persistent vars
    self.__state = {}
    try:
      if self.opt('persistence') and os.path.isfile(self.opt('state_file')):
        with open(self.opt('state_file'),'rb') as f:
          self.__state = pickle.load(f)
    except Exception as e:
      self.log_ex(e,'Unable to load persistent variables',
          'Unpickling of "%s" failed' % self.opt('state_file'))
    self.__persist = []

    # create protocol objects
    self.protocols = {name:proto(self,logging.getLogger(name))
        for (name,proto) in self.opt('protocols').items()}
    self.__fix_state(self.__state,[])

    # load plug-in hooks from this file
    self.hooks = {x:{} for x in ['chat','init','down','con','discon','recon',
        'rooms','roomf','msg','priv','group','status','err','idle','send']}
    self.log.info('Loading built-in commands from "sibylbot"')
    self.__load_funcs(self,'sibylbot')

    # exit if we failed to load plugin hooks from self.cmd_dir
    if not self.__load_plugins(self.opt('cmd_dir')):
      self.log.critical('Failed to load plugins; exiting')
      self.__fatal('duplicate @botcmd or @botfunc')

    # rename bot commands
    cmds = {}
    ns = {}
    success = True
    for (old,new) in self.opt('rename').items():
      if old in self.hooks['chat']:
        cmds[new] = self.hooks['chat'][old]
        ns[new] = self.ns_cmd[old]
      else:
        self.log.warning('Cannot rename %s:%s; no such cmd' % (new,old))
        success = False

    if not success:
      self.errors.append('(startup.sibyl) Some rename operations failed')

    for (old,new) in self.opt('rename').items():
      self.hooks['chat'][new] = cmds[new]
      self.ns_cmd[new] = ns[new]
      if old not in cmds:
        del self.hooks['chat'][old]
        del self.ns_cmd[old]

    # run plug-in init hooks and exit if there were errors
    if self.__run_hooks('init'):
      self.log.critical('Exception executing @botinit hooks; exiting')
      self.__fatal('a plugin\'s @botinit failed')

    self.__status = SibylBot.READY

  def __fatal(self,msg):
    """exit due to a fatal error"""

    self.log.critical('Fatal error during initialization')
    print '\n   *** Fatal error: %s (see log) ***\n' % msg
    print '   Config file: %s' % os.path.abspath(self.conf_file)
    print '   Cmd dir:     %s' % os.path.abspath(self.opt('cmd_dir'))
    print '   Log file:    %s\n' % os.path.abspath(self.opt('log_file'))
    sys.exit(1)

################################################################################
# BBB - Plug-in framework
################################################################################

  def __init_config(self):
    """search for and set all config options to default or user-specified"""

    dup_plugins = False
    duplicates = None

    # we need to get cmd_dir and chat_proto from the config file first
    # don't log the first set of default opts to avoid duplicates later
    self.conf = Config(self.conf_file)
    self.conf.reload(log=False)

    # check for duplicate plugin files
    (_,files) = util.rlistdir(self.opt('cmd_dir'))
    files = [os.path.splitext(x)[0] for x in files if
        ('__init__' not in x and x.split(os.path.extsep)[-1]=='py')]
    files = sorted(files,key=os.path.basename)
    files = [x for x in files if os.path.basename(x) not in self.opt('disable')]
    if self.opt('enable'):
      files = [x for x in files if os.path.basename(x) in self.opt('enable')]

    base_names = [os.path.basename(x) for x in files]
    if len(files)!=len(set(base_names)):
      dup = set([x for x in base_names if base_names.count(x)>1])
      dup_plugins = 'Multiple plugins named %s' % list(dup)

    # register config options from plugins
    for f in files:
      (d,f) = (os.path.dirname(f),os.path.basename(f))

      # import errors will be logged and handled in __load_plugins
      try:
        mod = util.load_module(f,d)
      except:
        continue

      duplicates = (not self.__load_conf(mod,f) or duplicates)

    # load protocol config options if protocols were loaded without errors
    if [x for x in self.opt('protocols').values() if x is not None]:
      for pname in self.opt('protocols'):
        mod = util.load_module('sibyl_'+pname,'protocols')
        duplicates = (not self.__load_conf(mod,pname) or duplicates)

    # now that we know all the options, read every option from the config file
    return (self.conf.reload(),dup_plugins,duplicates)

  def __load_plugins(self,d):
    """recursively load all plugins from all sub-directories"""

    success = True

    # build file list before-hand so we can check dependencies
    (_,files) = util.rlistdir(d)
    files = [x for x in files if
        (x.split(os.path.extsep)[-1]=='py' and '__init__' not in x)]
    files = sorted(files,key=os.path.basename)
    mods = {}

    # load hooks from every file
    for f in files:
      (d,f) = (os.path.dirname(f),os.path.basename(f))
      f = os.path.splitext(f)[0]

      # if "enable" is specified, only load plugins found in "enable"
      # the "disable" option overrides anything in the "enable" option
      if ((f not in self.opt('disable')) and
          ((not self.opt('enable')) or (f in self.opt('enable')))):
        self.log.info('Loading plugin "%s"' % f)

        try:
          mod = util.load_module(f,d)
        except Exception as e:
          msg = 'Error loading plugin "%s"' % f
          self.log_ex(e,msg)
          self.errors.append('(startup.sibyl) '+msg)
          continue

        mods[f] = mod
        success = (self.__load_funcs(mod,f) and success)
      else:
        self.log.debug('Skipping plugin "%s" (disabled in config)' % f)

    # check dependencies
    for (name,mod) in mods.items():
      if hasattr(mod,'__depends__'):
        for dep in mod.__depends__:
          if dep not in mods:
            success = False
            self.log.critical('Missing dependency "%s" from plugin "%s"'
                % (dep,name))
      if hasattr(mod,'__wants__'):
        for dep in mod.__wants__:
          if dep not in mods:
            self.log.warning('Missing plugin "%s" limits funcionality of "%s"'
                % (dep,name))

    self.plugins = sorted(mods.keys())

    return success

  def __load_funcs(self,mod,fil,silent=False):
    """load all hooks from the given module"""

    success = True

    for (name,func) in inspect.getmembers(mod,inspect.isroutine):

      # add @botfunc methods
      if getattr(func,'_sibylbot_dec_func',False):

        # check for duplicates
        if hasattr(self,name):
          self.log.critical('Duplicate @botfunc "%s" from "%s" and "%s"'
              % (name,self.ns_func[name],fil))
          success = False
          continue

        # set the function and ns_func
        setattr(self,name,func.__get__(self,SibylBot))
        self.ns_func[name] = fil
        if not silent:
          self.log.debug('  Registered function: %s.%s' % (fil,name))

      # add all other decorator hooks
      for (hook,dic) in self.hooks.items():
        if getattr(func,'_sibylbot_dec_'+hook,False):

          fname = getattr(func,'_sibylbot_dec_'+hook+'_name',None)

          if getattr(func,'_sibylbot_dec_chat',False):
            fname = fname.lower()

            # check for duplicate chat cmds
            if fname in dic:
              self.log.critical('Duplicate @botcmd "%s" from "%s" and "%s"'
                  % (fname,self.ns_cmd[fname],fil))
              success = False
              continue

            # check for invalid command names
            if not fname.replace('_','').isalnum():
              self.log.critical('Invalid @botcmd name "%s" for "%s" from "%s"'
                  % (fname,func.__name__,fil))
              success = False
              continue

          # register the hook
          s = '  Registered %s command: %s.%s = %s' % (hook,fil,name,fname)
          if fname is None:
            fname = fil+'.'+name
            s = '  Registered %s hook: %s.%s' % (hook,fil,name)
          dic[fname] = func

          # add chat hooks to ns_cmd
          if getattr(func,'_sibylbot_dec_chat',False):
            self.ns_cmd[fname] = fil

          if not silent:
            self.log.debug(s)

    return success

  def __load_conf(self,mod,ns):
    """load config hooks from the given module"""

    success = True

    # search for @botconf in the given module
    for (name,func) in inspect.getmembers(mod,inspect.isfunction):
      if getattr(func,'_sibylbot_dec_conf',False):
        opts = func(self)

        # conf.add_opts expects a list
        if not isinstance(opts,list):
          opts = [opts]

        # append module name to front of config options
        for opt in opts:
          opt['name'] = ns+'.'+opt['name']
        success = (success and self.conf.add_opts(opts,ns))

    return success

  def __fix_state(self,obj,done):
    """find Message, Room, User objects in the state and fix their protocols"""

    for x in done:
      if obj is x:
        return
    done.append(obj)
    if isinstance(obj,collections.Iterable) and not isinstance(obj,basestring):
      for x in obj:
        self.__fix_state(x,done)
        if isinstance(obj,dict):
          self.__fix_state(obj[x],done)
    else:
      if isinstance(obj,Message) or isinstance(obj,Room) or isinstance(obj,User):
        try:
          obj.protocol = self.protocols[obj.protocol]
        except KeyError:
          self.log.error('Error unpickling persistence; unknown protocol "%s"'
              % obj.protocol)

  def __run_hooks(self,hook,*args):
    """run and log the specified hooks passing args; don't use for idle hooks"""

    errors = {}

    # run all hooks of the given type
    for (name,func) in self.hooks[hook].items():
      if self.opt('log_hooks') or hook=='init':
        self.log.debug('Running %s hook: %s' % (hook,name))

      # catch exceptions, log them, and return them
      try:
        func(self,*args)
      except Exception as e:
        self.log_ex(e,'Exception running %s hook %s:' % (hook,name))
        errors[name] = e

    return errors

  def __run_idle(self):
    """run all idle hooks"""

    for (name,func) in self.hooks['idle'].items():

      t = time.time()
      if t<self.__idle_last.get(name,0)+getattr(func,'_sibylbot_dec_idle_freq'):
        continue
      self.__idle_last[name] = t

      try:
        if getattr(func,'_sibylbot_dec_idle_thread'):
          SmartThread(self,func,name=name).start()
        else:
          func(self)

        # we time idle hooks to make sure they aren't taking too long
        counts = self.__idle_count
        limit = self.opt('idle_time')
        if time.time()-t>limit:
          counts[name] = counts.get(name,0)+1
          count = self.opt('idle_count')
          self.log.warning('Idle hook %s exceeded %s sec (count=%s/%s)'
              % (name,limit,counts[name],count))
          if counts[name]>=count:
            self.log.critical('Deleting idle hook %s for taking too long'
                % name)
            del self.hooks['idle'][name]

        else:
          counts[name] = max(counts.get(name,0)-1,0)

      except Exception as e:
        self.log_ex(e,'Exception running idle hook %s:' % name)
        self.log.critical('Deleting idle hook %s' % name)
        del self.hooks['idle'][name]

################################################################################
# CCC - Callbacks for Protocols
################################################################################

  # @param mess (Message) the received Message
  # @assert mess is not from myself
  # @assert mess is from a user who is in one of our rooms
  def _cb_message(self,mess):
    """figure out if the message is a command and respond"""

    frm = mess.get_from()
    user = mess.get_user()
    usr = user.get_base()
    real = user.get_real()

    # Ignore messages from myself
    if real==mess.get_protocol().get_user():
      return

    if real:
      real = real.get_base()
    else:
      real = usr

    typ = mess.get_type()
    text = mess.get_text()

    # Execute status hooks or error hooks and return
    if typ==Message.STATUS:
      self.__run_hooks('status',mess)
      return
    elif typ==Message.ERROR:
      self.__run_hooks('err',mess)
      return

    # empty messages aren't relevant for anything else
    if not text.strip():
      return

    # check if the message contains a command
    cmd = self.__get_cmd(mess)
    cmd_list = cmd

    # only do further processing if the message was a command
    if cmd:

      # account for double cmd_prefix = redo (e.g. !!)
      if self.opt('cmd_prefix') and cmd.startswith(self.opt('cmd_prefix')):
        new = self.__remove_prefix(cmd)
        cmd = 'redo'
        if len(new.strip())>0:
          cmd += (' '+new.strip())

      # convert args to list accounting for quote blocking
      (cmd_name,args) = self.__get_args(cmd)
      cmd_list = [cmd_name]+args

    # Execute hooks even if cmd is None
    if typ==Message.PRIVATE:
      self.__run_hooks('priv',mess,cmd_list)
      self.__run_hooks('msg',mess,cmd_list)
    elif typ==Message.GROUP:
      self.__run_hooks('group',mess,cmd_list)
      self.__run_hooks('msg',mess,cmd_list)
    else:
      self.log.error('Unknown message type "%s"' % typ)
      return

    # now that hooks are done, return if there was no command
    if not cmd:
      return

    # check if the command exists
    if cmd_name not in self.hooks['chat']:
      self.log.info('Unknown command "%s"' % cmd_name)
      if typ==Message.GROUP:
        default_reply = None
      else:
        default_reply = self.MSG_UNKNOWN_COMMAND % {
          'command': cmd_name,
          'helpcommand': 'help',
        }
      reply = self.__unknown_command(mess,cmd_name,args)
      if reply is None:
        reply = default_reply
      if reply:
        self.__send(reply,frm)
      return

    # check against bw_list
    applied = self.match_bw(mess,cmd_name)
    ns = self.ns_cmd[cmd_name]
    pname = mess.get_protocol().get_name()
    if applied[0]=='b':
      self.log.info('FORBIDDEN: %s.%s from %s:%s with %s'
          % (ns,cmd_name,pname,real,applied))
      self.__send("You don't have permission to run \"%s\"" % cmd_name,frm)
      self.__stats['forbid'] += 1
      return

    # if the command was redo, retrieve the last command from that user
    if cmd_name=='redo':
      self.log.debug('Redo cmd; original msg: "'+text+'"')
      cmd = self.last_cmd.get(usr,'echo Nothing to redo')
      if len(args)>1:
        cmd += (' '+' '.join(args[1:]))
        self.last_cmd[usr] = cmd
      (cmd_name,args) = self.__get_args(cmd)
    elif cmd_name!='last':
      self.last_cmd[usr] = cmd

    self.log.info('CMD: %s.%s from %s:%s with %s' %
        (ns,cmd_name,pname,real,applied))

    # check for chat_ctrl
    func = self.hooks['chat'][cmd_name]
    if not self.opt('chat_ctrl') and func._sibylbot_dec_chat_ctrl:
      self.__send('chat_ctrl is disabled',frm)
      return

    # execute the command and catch exceptions
    reply = None
    self.__stats['cmds'] += 1
    try:
      if func._sibylbot_dec_chat_thread:
        self.log.debug('Spawning new thread for cmd "%s"' % cmd_name)
        SmartThread(self,func,mess,args).start()
      else:
        reply = func(self,mess,args)
    except Exception as e:
      self.__stats['ex'] += 1
      self.log_ex(e,
          'Error while executing cmd "%s":' % cmd_name,
          '  Message text: "%s"' % text)

      reply = self.MSG_ERROR_OCCURRED
      if self.opt('except_reply'):
        reply = traceback.format_exc(e).split('\n')[-2]
    if reply:
      self.__send(reply,frm)

  # @param room (str) the room we successfully joined
  def _cb_join_room_success(self,room):
    """execute callbacks on successfull MUC join"""

    self.__run_hooks('rooms',room)

  # @param room (str) the room we failed to join
  # @param error (str) the human-readable reason we failed to join
  def _cb_join_room_failure(self,room,error):
    """execute callbacks on successfull MUC join"""

    self.__run_hooks('roomf',room,error)

################################################################################
# DDD - Helper functions
################################################################################

  def __get_cmd(self,mess):
    """return the body of mess with nick and prefix removed, or None"""

    text = mess.get_text().strip()
    frm = mess.get_user()
    room = mess.get_room()
    proto = mess.get_protocol()

    direct = False
    prefix = False

    # if text starts with our nick name, remove it
    if mess.get_type()==Message.GROUP:
      nick = proto.get_nick(room).lower()
      if proto.in_room(room) and text.lower().startswith(nick):
        direct = True
    else:
      if text.lower().startswith(self.opt('nick_name')):
        direct = True
    if direct:
      text = text[len(self.opt('nick_name')):].strip()

    # if text starts with cmd_prefix, remove it
    text = self.__remove_prefix(text)
    prefix = (text!=mess.get_text().strip())

    # always respond to private msgs
    if mess.get_type()==Message.PRIVATE:
      return text

    # for group msgs check if only_direct and/or cmd_prefix are set/fulfilled
    else:
      if ((not self.opt('only_direct')) and (not self.opt('cmd_prefix')) or
          ((self.opt('only_direct') and direct) or
          (self.opt('cmd_prefix') and prefix))):
        return text
    return None

  def __remove_prefix(self,text):
    """remove the command prefix from the given text"""

    if not self.opt('cmd_prefix'):
      return text
    if not text.startswith(self.opt('cmd_prefix')):
      return text
    return text[len(self.opt('cmd_prefix')):]

  def __get_args(self,cmd):
    """return the cmd_name and args in a tuple, accounting for quotes"""

    args = cmd.split(' ')
    name = args[0].lower()
    args = ' '.join(args[1:]).strip()

    l = []
    if args:
      l = util.get_args(args)

    return (name,l)

  def __get_plugin(self,func):
    """return the name of the plug-in containing the given function"""

    filename = os.path.basename(inspect.getfile(func))
    return os.path.extsep.join(filename.split(os.path.extsep)[:-1])

  def __send(self,text,to,bcast=False,frm=None,users=None,hook=True):
    """actually send a message"""

    if isinstance(text,str):
      text = text.decode('utf8')
    elif not isinstance(text,unicode):
      text = unicode(text)

    if bcast:
      if self.has_plugin('room') and self.opt('room.bridge_broadcast'):
        users = (users or [])
        for room in self.get_bridged(to):
          nick = room.get_protocol().get_nick(room)
          users += [u for u in room.get_occupants() if u.get_name()!=nick]
      text = to.get_protocol().broadcast(text,to,frm,users)
    else:
      to.get_protocol().send(text,to)

    if hook:
      self.__run_hooks('send',text,to)

  def __match_user(self,mess,rule_str):
    """check if the black/white text matches protocol, user, room"""

    rule = rule_str.split(':')
    rule[0] = rule[0].lower()
    if len(rule)>2:
      rule[2] = ':'.join(rule[2:])
    proto = self.protocols.get(rule[1],None)
    if not proto:
      return False

    # Match protocols
    if rule[0]=='p':
      return proto==mess.get_protocol()

    # Match rooms
    elif rule[0]=='r':
      return proto.new_room(rule[2])==mess.get_room()

    # Match users
    elif rule[0]=='u':
      return proto.new_user(rule[2]).base_match(mess.get_user().get_real())

  def __match_cmd(self,name,rule_str):
    """check if the black/white text matches plugin, cmd"""

    rule = rule_str.split(os.path.extsep)

    # If it ends in '.py' it's a plugin name
    if (len(rule)>1) and (rule[1]=='py') and (rule[0] in self.plugins):
      return rule[0]==self.ns_cmd[name]

    # Otherwise it's a command name
    else:
      return rule_str==name

  def __defer(self,msg):
    """add messages to __deferred_priv"""

    d = self.__deferred
    c = self.__deferred_count

    to = msg[1]
    proto = to.get_protocol()
    drop = None
    if len(d)>self.opt('defer_total'):
      drop = lambda m: True
    elif c.get(proto,0)>self.opt('defer_proto'):
      drop = lambda m: m[1].get_protocol()==proto
    elif ((isinstance(to,Room) and c.get(to,0)>self.opt('defer_room'))
        or (isinstance(to,User) and c.get(to,0)>self.opt('defer_priv'))):
      drop = lambda m: m[1]==to

    if drop:
      for i in range(0,len(d)):
        if drop(d[i]):
          del d[i]
          break

    c[proto] = c.get(proto,0)+1
    c[to] = c.get(to,0)+1
    d.append(msg)
    self.log.debug('Deferring msg for "%s:%s" (now %s in queue)'
        % (proto.get_name(),to,len(d)))

  def __requeue(self,match):
    """helper function for requeueing msgs"""

    d = self.__deferred
    c = self.__deferred_count

    i = 0
    re = 0
    while i<len(self.__deferred):
      msg = d[i]
      to = msg[1]
      proto = to.get_protocol()
      if match(msg):
        self.__pending_send.put(msg)
        c[proto] -= 1
        if c[proto]==0:
          del c[proto]
        c[to] -= 1
        if c[to]==0:
          del c[to]
        del d[i]
        re += 1
      else:
        i += 1

    if re:
      self.log.debug('Requeued %s msgs (now %s in queue)' % (re,len(d)))

################################################################################
# EEE - Chat commands
#
# When we call functions from plugins, we must pass "self" explicitly. However,
# the below functions are bound, and so pass "self" implicitly as well. If we
# called func(self,s) for one of the below functions, the function would
# actually receive func(self,self,s). The @staticmethod decorator fixes this.
#
################################################################################

  @staticmethod
  @botcmd(name='redo')
  def __redo(self,mess,args):
    """redo last command - redo [args]"""

    # this is a dummy function so it gets displayed in the help command
    # the real logic is at the end of callback_message()
    return

  @staticmethod
  @botcmd(name='last')
  def __last(self,mess,args):
    """display last command (from any chat)"""

    return self.last_cmd.get(mess.get_from().get_base(),'No past commands')

  @staticmethod
  @botcmd(name='git')
  def __git(self,mess,args):
    """return a link to the github page"""

    return 'https://github.com/TheSchwa/sibyl'

  @staticmethod
  @botcmd(name='about')
  def __about(self,mess,args):
    """print version and some plug-in info"""

    cmds = len(self.hooks['chat'])
    funcs = self.hooks['chat'].values()
    plugins = sorted(self.plugins+['sibylbot'])
    protos = ','.join(sorted(self.opt('protocols').keys()))
    return ('Sibyl %s (%s) --- %s commands from %s plugins: %s'
        % (__version__,protos,cmds,len(plugins),plugins))

  @staticmethod
  @botcmd(name='hello')
  def __hello(self,mess,args):
    """reply if someone says hello"""

    return 'Hello world!'

  @staticmethod
  @botcmd(name='help')
  def __help(self,mess,args):
    """return help info about cmds - help [cmd]"""

    if not args:
      if self.__doc__:
        description = self.__doc__.strip()
      else:
        description = 'Available commands:'

      usage = sorted([
        '%s.%s: %s' % (self.__get_plugin(cmd),name,
            (cmd.__doc__ or '(undocumented)').strip().split('\n', 1)[0])
        for (name, cmd) in self.hooks['chat'].iteritems()
          if not cmd._sibylbot_dec_chat_hidden
      ])
      if not self.opt('help_plugin'):
        usage = sorted(['.'.join(x.split('.')[1:]) for x in usage])
      usage = '\n'.join(usage)
      usage = '\n\n' + '\n\n'.join(filter(None,
        [usage, self.MSG_HELP_TAIL % {'helpcommand': 'help'}]))
    else:
      description = ''
      args = self.__remove_prefix(args[0])
      if args in self.hooks['chat']:
        func = self.hooks['chat'][args]
        plugin = self.__get_plugin(func)
        usage = (('[%s] %s' % (plugin,func.__doc__)) or 'undocumented').strip()
      else:
        usage = self.MSG_HELP_UNDEFINED_COMMAND

    top = self.__top_of_help_message()
    bottom = self.__bottom_of_help_message()
    return ''.join(filter(None, [top, description, usage, bottom]))

  @staticmethod
  @botcmd(name='errors')
  def __errors(self,mess,args):
    """list errors - errors [search1 search2]"""

    if not self.errors:
      return 'No errors'

    if not args:
      args = ['-startup']
    matches = util.matches(self.errors,args,sort=False)

    if not matches:
      return 'No matching errors'
    return ', '.join(matches)

  @staticmethod
  @botcmd(name='stats')
  def __stats_cmd(self,mess,args):
    """respond with some stats"""

    return (('Born: %s --- Cmds-Run: %s --- Cmds-Forbid: %s --- ' +
        'Cmds-Error: %s --- Disconnects: %s') %
        (time.asctime(time.localtime(self.__stats['born'])),
        self.__stats['cmds'],self.__stats['forbid'],
        self.__stats['ex'],self.__stats['discon']))

  @staticmethod
  @botcmd(name='uptime')
  def __uptime(self,mess,args):
    """respond with the bot's current uptime"""

    diff = time.time()-self.__stats['born']
    days = int(diff/(60*60*24))
    hrs = int((diff % (60*60*24))/(60*60))
    mins = int((diff % (60*60))/60)
    secs = diff % 60

    return 'Up for %s days and %.2d:%.2d:%.2d' % (days,hrs,mins,secs)

################################################################################
# FFF - UI Functions
################################################################################

  def __unknown_command(self, mess, cmd, args):
    """Default handler for unknown commands

    Override this method in derived class if you
    want to trap some unrecognized commands.  If
    'cmd' is handled, you must return some non-false
    value, else some helpful text will be sent back
    to the sender.
    """
    return None

  def __top_of_help_message(self):
    """Returns a string that forms the top of the help message

    Override this method in derived class if you
    want to add additional help text at the
    beginning of the help message.
    """
    return ""

  def __bottom_of_help_message(self):
    """Returns a string that forms the bottom of the help message

    Override this method in derived class if you
    want to add additional help text at the end
    of the help message.
    """
    return ""

################################################################################
# GGG - Run and Stop Functions
################################################################################

  def __log_startup_msg(self):
    """log a message to appear when the bot is initialising"""

    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')
    self.log.critical('SibylBot starting...')
    self.log.info('')
    self.log.info('Conf : '+os.path.abspath(self.conf_file))
    self.log.info('PID  : %s' % os.getpid())
    self.log.info('')
    self.log.info('Reading config file "%s"...' % self.conf_file)

  def __log_connect_msg(self):
    """log a message to appear when the bot connects"""

    self.log.info('')
    self.log.info('SibylBot connecting...')
    self.log.info('')

    for (name,proto) in self.protocols.items():
      self.log.info('Chat : %s' % name)
      self.log.info('User : %s' % proto.get_user())
      for room in self.opt('rooms').get(name,[]):
        self.log.info('Room : %s/%s' %
            (room['room'],(room['nick'] if room['nick'] else 'Sibyl')))
      self.log.info('')

    self.log.info('Plug : %s' % ','.join(self.plugins))
    self.log.info('Cmds : %i' % len(self.hooks['chat']))
    self.log.info('Log  : %s' %
        logging.getLevelName(self.log.getEffectiveLevel()))
    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')

  # see note in section EEE comment header regarding @staticmethod
  @staticmethod
  @botrooms
  def __tell_errors(self,room):
    """mention startup errors in rooms we join on init"""

    if room in self.__tell_rooms:
      del self.__tell_rooms[self.__tell_rooms.index(room)]
      if self.errors:
        msg = 'Errors during startup: '
        self.__send(msg+self.run_cmd('errors',['startup']),room,hook=False)
    if not self.__tell_rooms:
      self.del_hook(self.__tell_errors)

  def __serve(self):
    """process loop - connect and process messages"""

    for (name,proto) in self.protocols.items():
      if proto.is_connected():
        proto.process()
      else:
        if (name not in self.__recons) or (self.__recons[name]<time.time()):
          self.__run_hooks('recon',name)
          proto.connect()
          self.__run_hooks('con',name)
          for room in self.opt('rooms').get(name,[]):
            pword = room['pass'] and room['pass'].get()
            proto.join_room(proto.new_room(room['room'],room['nick'],pword))
          if name in self.__recons:
            del self.__recons[name]

  def __run_forever(self):
    """reconnect loop - catch known exceptions"""

    if self.opt('tell_errors'):
      for (pname,rooms) in self.opt('rooms').items():
        for room in rooms:
          room = self.protocols[pname].new_room(room['room'])
          self.__tell_rooms.append(room)

    # try to reconnect forever unless self.quit()
    while not self.__finished:
      try:
        self.__serve()
        self.__idle_proc()
        time.sleep(0.1)

      except (PingTimeout,ConnectFailure,ServerShutdown) as e:
        name = e.protocol
        proto = self.protocols[name]
        proto.disconnected()
        self.__run_hooks('discon',name,e)
        self.__stats['discon'] += 1

        if not self.opt('catch_except'):
          raise e

        reason = {PingTimeout:'ping timeout',
                  ConnectFailure:'unable to connect',
                  ServerShutdown:'server shutdown'}
        for r in reason:
          if isinstance(e,r):
            reason = reason[r]
            break
        proto.log.error('Connection lost ('+reason+
            '); retrying in '+str(self.opt('recon_wait'))+' sec')

        self.__recons[name] = time.time()+self.opt('recon_wait')

      except AuthFailure as e:
        name = e.protocol
        self.log.error('Disabling protocol "%s" due to AuthFailure' % name)
        del self.protocols[name]
        if not self.protocols:
          self.quit('No active protocols; exiting')

      except KeyboardInterrupt:
        self.quit('stopped by KeyboardInterrupt')
      except SigTermInterrupt:
        self.quit('stopped by SIGTERM')

  def __idle_proc(self):
    """This function will be called in the main loop."""

    self.__idle_del()
    self.__idle_send()

    if (self.opt('idle_count')>0
        and time.time()>=self.__last_idle+self.opt('idle_freq')):
      self.__run_idle()
      self.__last_idle = time.time()

  def __idle_del(self):
    """deleted queued hooks"""

    while not self.__pending_del.empty():
      (func,dec) = self.__pending_del.get()

      if not dec:
        decs = self.hooks.keys()
      else:
        decs = [dec]

      for dec in decs:
        hooks = self.hooks[dec]
        for name in hooks.keys():
          if hooks[name]==func:
            self.log.debug('Deleting %s hook %s' % (dec,name))
            del hooks[name]
            if dec=='chat':
              del self.ns_cmd[name]

  def __idle_send(self):
    """send queued messages synchronously"""

    while not self.__pending_send.empty():
      try:
        msg = self.__pending_send.get()
        if (msg[1].get_protocol().is_connected() and
            (isinstance(msg[1],User) or msg[1].get_protocol().in_room(msg[1]))):
          self.__send(*msg)
        else:
          self.__defer(msg)
      except ProtocolError as e:
        self.__defer(msg)
        if msg[1].get_protocol().is_connected():
          raise e
      except Exception as e:
        self.log_ex(e,'Error sending %s msg' % msg[1].get_protocol().get_name())

  @staticmethod
  @botcon
  def __requeue_priv(bot,pname):
    """requeue deferred private messages on protocol connect"""
    bot.__requeue(lambda m: m[1].get_protocol().get_name()==pname
        and isinstance(m[1],User))

  @staticmethod
  @botrooms
  def __requeue_group(bot,room):
    """requeue deferred group messages on room join"""
    bot.__requeue(lambda m: m[1]==room)

################################################################################
# HHH - User-facing functions
################################################################################

  def run_forever(self):
    """run the bot catching any unhandled exceptions"""

    self.__status = SibylBot.RUNNING

    # unfortunately xmpppy has a couple print statements, so kill stdout
    if self.opt('kill_stdout'):
      sys.stdout = open(os.devnull,'wb')

    self.__log_connect_msg()

    # catch unhandled Exceptions and write traceback to the log
    try:
      self.__run_forever()

      # send any pending messages before disconnecting
      self.__idle_send()

    except Exception as e:
      self.log.critical('UNHANDLED: %s\n\n%s' %
          (e.__class__.__name__,traceback.format_exc(e)))
      self.log.critical(self.MSG_UNHANDLED)

    # shutdown cleanly
    for proto in self.protocols.values():
      proto.shutdown()
    self.__run_hooks('down')

    if self.opt('persistence'):
      d = {}
      for name in self.__persist:
        d[name] = getattr(self,name)
      with open(self.opt('state_file'),'wb') as f:
        pickle.dump(d,f,-1)

    sys.stdout = sys.__stdout__
    self.__status = SibylBot.EXITED
    return self.__reboot

  # this function is thread-safe
  # @param text (str,unicode) the text to send
  # @param to (User,Room) the recipient
  # @param broadcast (bool) [False] highlight all users (only works for Rooms)
  # @param frm (User) [None] the sending user (only relevant for broadcast)
  # @param users (list of User) [None] additional users to highlight (broadcast)
  # @param hook (bool) [True] execute @botsend hooks for this message
  #   NOTE: when @botsend hooks call send(), they MUST set hook=False
  def send(self,text,to,broadcast=False,frm=None,users=None,hook=True):
    """send a message (this function is thread-safe)"""

    broadcast = (broadcast and isinstance(to,Room))
    frm = (frm if broadcast else None)
    users = (users if broadcast else None)
    self.__pending_send.put((text,to,broadcast,frm,users,hook))

  # @param (str) the name of a protocol
  # @return (Protocol) the Protocol object with that name
  def get_protocol(self,name):
    """return the Protocol object with the given name"""

    return self.protocols[name]

  # @param msg (str) [None] message to log
  def quit(self,msg=None):
    """Stop serving messages and exit"""

    self.__finished = True
    if msg:
      self.log.critical(msg)
    else:
      self.log.critical('SibylBot.quit() called, but no reason given')

  # @param msg (str) [None] message to log
  def reboot(self,msg=None):
    """Reboot the bot"""

    self.__reboot = True
    if msg is None:
      msg = 'SibylBot.reboot() called, but no reason given'
    self.quit(msg)

  # @param name (str) [None] name of the opt to fetch
  # @return (object) the value of the opt or the entire opt dict if no name
  def opt(self,name=None):
    """return the value of the specified config option"""

    if not name:
      return self.conf.opts
    return self.conf.opts[name]

  # @param name (str) name of the instance variable to set
  # @param val (object) [None] value to set
  # @param persist (bool) [False] save/load this var on bot start/stop
  # @raise (AttributeError) if the var already exists
  def add_var(self,name,val=None,persist=False):
    """add a var to the bot, or raise an exception if it already exists"""

    caller = util.get_caller()
    if hasattr(self,name):
      space = self.ns_opt.get(name,'sibylbot')
      self.log.critical('plugin "%s" tried to overwrite var "%s" from "%s"'
          % (caller,name,space))
      raise DuplicateVarError

    if self.opt('persistence') and persist:
      val = self.__state.get(name,val)
      self.__persist.append(name)

    setattr(self,name,val)
    self.ns_opt[name] = caller

  # @param cmd (str) name of chat cmd to run
  # @param args (list) [None] arguments to pass to the command
  # @param mess (Message) [None] message to pass to the command
  # @param check_bw (bool) [True] enforce bw_list rules (if mess also supplied)
  # @return (str,None) the result of the command
  def run_cmd(self,cmd,args=None,mess=None,check_bw=True):
    """run a chat command manually"""

    check_bw = (check_bw and mess)

    # catch invalid arguments to help developers
    if (args is not None) and (not isinstance(args,list)):
      raise ValueError('The args to run_cmd must be list')

    if args is None:
      args = []

    applied = self.match_bw(mess,cmd) if check_bw else '(check_bw=False)'
    ns = self.ns_cmd[cmd]
    if applied[0]=='b':
      self.log.debug('  FORBIDDEN: %s.%s via run_cmd() with %s'
          % (ns,cmd,applied))
      return 'You do not have permission to run "%s"' % cmd

    self.log.debug('  CMD: %s.%s via run_cmd() with %s' %
        (ns,cmd,applied))
    return self.hooks['chat'][cmd](self,mess,args)

  # @param msg (str) the message to log
  # @param ns (str) an identifier for the caller (e.g. plugin name)
  def error(self,msg,ns):
    """add an error to the bot's list accessible via the error chat cmd"""

    if self.__status==SibylBot.INIT:
      ns = 'startup.'+ns
    self.errors.append('(%s) %s' % (ns,msg))

  # @param ex (Exception) the exception to log
  # @param short_msg (str) text to log at logging.ERROR
  # @param long_msg (str) [None] text to log at logging.DEBUG
  def log_ex(self,ex,short_msg,long_msg=None):
    """log the exception name (logging.ERROR) and traceback (logging.DEBUG)"""

    full = traceback.format_exc(ex)
    short = full.split('\n')[-2]

    self.log.error(short_msg)
    self.log.error('  %s' % short)
    if long_msg:
      self.log.debug(long_msg)
    self.log.debug(full)

  # this function is thread-safe
  # @param func (Function) the function to remove from our hooks
  # @param dec (str) the hook type to remove e.g. 'chat', 'mess', 'rooms'
  def del_hook(self,func,dec=None):
    """delete a hook (this function is thread-safe)"""

    self.__pending_del.put((func,dec))

  # @param plugin (str) [None] name of plugin to check for, or return all
  # @return (bool,list) True if the plugin was loaded, or list all
  def has_plugin(self,plugin=None):
    """check if a plugin was loaded"""

    if not plugin:
      return self.plugins
    return (plugin in self.plugins)

  # @param mess (Message) the originating message
  # @param cmd_name (str) the command name being run
  # @return (tuple(str,str,str)) a 3-tuple with fields in order:
  #     str: either 'w' or 'b' for white/black-listed
  #     str: either '*' for all, or the name of a protocol/room/user
  #     str: either '*' for all, or the name of a command/plugin
  def match_bw(self,mess,cmd_name):
    """find the matching bw_list entry for the message"""

    pname = mess.get_protocol().get_name()
    if pname in self.opt('admin_protos'):
      applied = ('w','proto:'+pname,'*')
    else:
      for rule in self.opt('bw_list'):
        if (rule[1]!='*') and (not self.__match_user(mess,rule[1])):
          continue
        if (rule[2]!='*') and (not self.__match_cmd(cmd_name,rule[2])):
          continue
        applied = rule
    return applied

  # @param name (str) name of the command to check
  # @return (None,str) the namespace of the command, or None if it doesn't exist
  def which(self,name):
    """get the function for a given command"""

    return self.ns_cmd.get(name,None)

  # @param func (Function) the function to run when the command is received
  # @param ns (str) the namespace of the command (e.g. plugin name, or w/e)
  # @param name (str) [func.__name__] the name of the command to register
  # @param ctrl (bool) [False] if this function requires chat_ctrl be set
  # @param hidden (bool) [False] whether to hide this function from the help cmd
  # @param thread (bool) [False] if True execute the command in its own thread
  # @return (bool) False if the command already exists, True if successful
  # @raise (ValueError) if the namd given is invalid
  def register_cmd(self,func,ns,name=None,ctrl=False,hidden=False,thread=False):
    """register a new chat command"""

    name = (name or func.__name__).lower()
    func._sibylbot_dec_chat_ctrl = ctrl
    func._sibylbot_dec_chat_hidden = hidden
    func._sibylbot_dec_chat_thread = thread

    if not name.replace('_','').isalnum():
      raise ValueError('Chat commands must be alphanumeric+underscore')
    func._sibylbot_dec_chat_name = name

    if name in self.hooks['chat']:
      return False

    self.hooks['chat'][name] = func
    self.ns_cmd[name] = ns
    self.log.debug('  Registered chat command: %s.%s = %s'
        % (ns,func.__name__,name))
    return True

  # @param name (str) name of the chat command to unregister
  def del_cmd(self,name):
    """unregisters a chat command"""

    func = self.hooks['chat'].get(name.lower(),None)
    self.del_hook(func,'chat')

  # @param func (Function) the idle hook to modify
  # @param freq (int) the number of seconds to wait between hook executions
  # @return (bool) if the hook exists and the new freq is valid
  def set_idle_freq(self,func,freq):
    """set the frequency of an idle hook"""

    if not isinstance(freq,int):
      raise TypeError('Idle freq must be an integer')
    if (freq<bot.opt('idle_freq')) or (func not in bot.hooks['idle']):
      return False

    bot.hooks['idle'][func]._sibylbot_dec_idle_freq = freq
    return True
