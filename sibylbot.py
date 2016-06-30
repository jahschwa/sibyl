#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2016 Joshua Haas <jahschwa.com>
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

import sys,logging,re,os,imp,inspect,traceback,time

from lib.config import Config
from lib.protocol import Message
from lib.protocol import PingTimeout,ConnectFailure,AuthFailure,ServerShutdown
from lib.decorators import botcmd
import lib.util as util

__author__ = 'Joshua Haas <haas.josh.a@gmail.com>'
__version__ = 'v6.0.0'
__website__ = 'https://github.com/TheSchwa/sibyl'
__license__ = 'GNU General Public License version 3 or later'

class DuplicateVarError(Exception):
  pass

################################################################################
# AAA - SibylBot                                                               #
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

  def __init__(self,conf_file='sibyl.conf'):
    """create a new sibyl instance, load: conf, protocol, plugins"""

    # create "namespace" dicts to keep track of who added what for error msgs
    self.ns_opt = {}
    self.ns_func = {}
    self.ns_cmd = {}

    # load config to get cmd_dir and chat_proto
    self.conf_file = conf_file
    (result,duplicates) = self.__init_config()

    # configure logging
    logging.basicConfig(filename=self.opt('log_file'),
        format='%(asctime).19s | %(name)-8.8s | %(levelname).3s | %(message)s',
        level=self.opt('log_level'))
    self.log = logging.getLogger('sibylbot')
    self.__log_startup_msg()

    # log config errors and check for success
    self.conf.process_log()
    if result==Config.FAIL or duplicates:
      self.log.critical('Error parsing config file; exiting')
    elif result==Config.ERRORS:
      self.log.warning('Parsed config file with warnings')

    # if we are missing required config options exit with status message
    if result==Config.FAIL or duplicates:
      self.__fatal('unusuable config')

    self.log.info('Success parsing config file')
    self.log.info('')

    # create protocol object
    self.protocol = self.opt('chat_proto')[1](
        self,logging.getLogger(self.opt('chat_proto')[0]))

    # initialise variables
    self.__finished = False
    self.last_cmd = {}

    # load plug-in hooks from this file
    self.hooks = {x:{} for x in ['chat','init','down','con','discon','recon',
        'mucs','mucf','msg','priv','group','status','err','idle']}
    self.__load_funcs(self,'sibylbot',silent=True)

    # exit if we failed to load plugin hooks from self.cmd_dir
    if not self.__load_plugins(self.opt('cmd_dir')):
      self.log.critical('Failed to load plugins; exiting')
      self.__fatal('duplicate @botcmd or @botfunc')

    # run plug-in init hooks and exit if there were errors
    if self.__run_hooks('init'):
      self.log.critical('Exception executing @botinit hooks; exiting')
      self.__fatal('a plugin\'s @botinit failed')

  def __fatal(self,msg):
    """exit due to a fatal error"""

    print '\n   *** Fatal error: %s (see log) ***\n' % msg
    print '   Config file: %s' % os.path.abspath(self.conf_file)
    print '   Cmd dir:     %s' % os.path.abspath(self.opt('cmd_dir'))
    print '   Log file:    %s\n' % os.path.abspath(self.opt('log_file'))
    sys.exit(1)

################################################################################
# BBB - Plug-in framework                                                      #
################################################################################

  def __init_config(self):
    """search for and set all config options to default or user-specified"""

    duplicates = False

    # we need to get cmd_dir and chat_proto from the config file first
    self.conf = Config(self.conf_file)

    # don't log the first set of default opts to avoid duplicates later
    self.conf.logging = False
    self.conf.reload()
    self.conf.logging = True

    # check for duplicate plugin files
    files = [os.path.splitext(x)[0] for x in
        util.rlistfiles(self.opt('cmd_dir')) if
        ('__init__' not in x and x.endswith('.py'))]
    files = sorted(files,key=os.path.basename)
    files = [x for x in files if os.path.basename(x) not in self.opt('disable')]
    if self.opt('enable'):
      files = [x for x in files if x in self.opt('enable')]

    base_names = [os.path.basename(x) for x in files]
    if len(files)!=len(set(base_names)):
      dup = set([x for x in base_names if base_names.count(x)>1])
      raise RuntimeError('Multiple plugins named %s' % list(dup))

    # load config options from plugins
    for f in files:
      (d,f) = (os.path.dirname(f),os.path.basename(f))
      mod = util.load_module(f,d)
      duplicates = (not self.__load_conf(mod,f) or duplicates)

    # load chat protocol config options if chat_proto was set in the config
    if self.opt('chat_proto'):
      pname = self.opt('chat_proto')[0]
      mod = util.load_module('sibyl_'+pname,'protocols')
      duplicates = (not self.__load_conf(mod,pname) or duplicates)

    # now that we know all the options, read every option from the config file
    return (self.conf.reload(),duplicates)

  def __load_plugins(self,d):
    """recursively load all plugins from all sub-directories"""

    success = True

    # build file list before-hand so we can check dependencies
    files = [x for x in util.rlistfiles(d) if x.endswith('.py')]
    files = [x for x in files if '__init__' not in x]
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
        mod = util.load_module(f,d)
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
            self.log.critical('Missing dependency "%s" from plugin "%s"' %
                (dep,name))
      if hasattr(mod,'__wants__'):
        for dep in mod.__wants__:
          if dep not in mods:
            self.log.warning('Missing plugin "%s" limits funcionality of "%s"' %
                (dep,name))

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
          self.log.critical('Duplicate @botfunc "%s" from "%s" and "%s"' %
              (name,self.ns_func[name],fil))
          success = False
          continue

        # set the function and ns_func
        setattr(self,name,self.__bind(func))
        self.ns_func[name] = fil
        if not silent:
          self.log.debug('  Registered function: %s.%s' % (fil,name))

      # add all other decorator hooks
      for (hook,dic) in self.hooks.items():
        if getattr(func,'_sibylbot_dec_'+hook,False):

          fname = getattr(func,'_sibylbot_dec_'+hook+'_name',None)
          
          # check for duplicate chat cmds
          if getattr(func,'_sibylbot_dec_chat',False):
            if fname in dic:
              self.log.critical('Duplicate @botcmd "%s" from "%s" and "%s"' %
                  (fname,self.ns_cmd[fname],fil))
              success = False
              continue

          # register the hook
          s = '  Registered %s command: %s.%s = %s' % (hook,fil,name,fname)
          if fname is None:
            fname = fil+'.'+name
            s = '  Registered %s hook: %s.%s' % (hook,fil,name)
          dic[fname] = self.__bind(func)
          
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
        success = (success and self.conf.add_opts(opts,ns))

    return success

  def __bind(self,func):
    """bind the given function to self"""

    return func.__get__(self,SibylBot)

  def __run_hooks(self,hook,*args):
    """run and log the specified hooks passing args"""

    errors = {}

    # run all hooks of the given type
    for (name,func) in self.hooks[hook].items():
      if hook!='idle':
        self.log.debug('Running %s hook: %s' % (hook,name))

      # catch exceptions, log them, and return them
      try:
        func(*args)
      except Exception as e:
        full = traceback.format_exc(e)
        short = full.split('\n')[-2]

        self.log.error('Exception running %s hook %s:' % (hook,name))
        self.log.error('  '+short)
        self.log.debug(full)

        # disable idle hooks so that don't keep raising exceptions
        if hook=='idle':
          self.log.critical('Disabling idle hook %s' % name)
          del self.hooks['idle'][name]

        errors[name] = e

    return errors

  def __idle_proc(self):
    """This function will be called in the main loop."""

    self.__run_hooks('idle')

################################################################################
# CCC - Callbacks for Protocols                                                #
################################################################################

  # @param mess (Message) the received Message
  # @assert mess is not from myself
  # @assert mess is from a user who is in one of our rooms
  def _cb_message(self,mess):
    """figure out if the message is a command and respond"""

    frm = mess.get_from()
    usr = frm.get_base()
    real = frm.get_real()
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
    if not text:
      return

    # check if the message contains a command
    cmd = self.__get_cmd(mess)

    # Execute hooks, return if ERROR
    if typ==Message.PRIVATE:
      self.__run_hooks('priv',mess,cmd)
      self.__run_hooks('msg',mess,cmd)
    elif typ==Message.GROUP:
      self.__run_hooks('group',mess,cmd)
      self.__run_hooks('msg',mess,cmd)
    else:
      self.log.error('Unknown message type "%s"' % typ)
      return

    # if cmd is None, the msg was not a chat cmd
    if not cmd:
      return
    
    # account for double cmd_prefix = redo (e.g. !!)
    if self.opt('cmd_prefix') and cmd.startswith(self.opt('cmd_prefix')):
      new = self.__remove_prefix(cmd)
      cmd = 'redo'
      if len(new.strip())>0:
        cmd += (' '+new.strip())

    # convert args to list accounting for quote blocking
    (cmd_name,args) = self.__get_args(cmd)

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
        self.protocol.send(reply,frm)
      return
    
    # check against bw_list
    for rule in self.opt('bw_list'):
      if (rule[1]!='*') and (rule[1] not in real):
        continue
      if (rule[2]!='*') and (rule[2]!=cmd_name):
        continue
      applied = rule
    if applied[0]=='b':
      self.protocol.send("You don't have permission to run that command",frm)
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

    self.log.info('CMD: %s from %s with %s' % (cmd_name,real,applied))

    # check for chat_ctrl
    func = self.hooks['chat'][cmd_name]
    if not self.opt('chat_ctrl') and func._sibylbot_dec_chat_ctrl:
      self.protocol.send('chat_ctrl is disabled',frm)
      return

    # execute the command and catch exceptions
    try:
      reply = func(mess,args)
    except Exception, e:
      full = traceback.format_exc(e)
      short = full.split('\n')[-2]

      self.log.error('Error while executing cmd "%s":' % cmd_name)
      self.log.error('  %s' % short)
      self.log.debug('  Message text: "%s"' % text)
      self.log.debug(full)

      reply = self.MSG_ERROR_OCCURRED
      if self.opt('except_reply'):
        reply = short
    if reply:
      self.protocol.send(reply,frm)

  # @param room (str) the room we successfully joined
  def _cb_join_room_success(self,room):
    """execute callbacks on successfull MUC join"""

    self.__run_hooks('mucs',room)

  # @param room (str) the room we failed to join
  # @param error (str) the human-readable reason we failed to join
  def _cb_join_room_failure(self,room,error):
    """execute callbacks on successfull MUC join"""

    result = self.__run_hooks('mucf',room,error)

################################################################################
# DDD - Helper functions                                                       #
################################################################################

  def __get_cmd(self,mess):
    """return the body of mess with nick and prefix removed, or None"""

    text = mess.get_text()
    frm = mess.get_from()

    direct = False
    prefix = False

    # if text starts with our nick name, remove it
    if mess.get_type()==Message.GROUP:
      room = frm.get_room()
      nick = self.protocol.get_nick(room).lower()
      if self.protocol.in_room(room) and text.lower().startswith(nick):
        direct = True
    else:
      if text.lower().startswith(self.opt('nick_name')):
        direct = True
    if direct:
      text = ' '.join(text.split(' ',1)[1:])

    # if text starts with cmd_prefix, remove it
    text = self.__remove_prefix(text)
    prefix = (text!=mess.get_text())

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
    name = args[0]
    args = ' '.join(args[1:]).strip()

    l = []
    if args:
      l = util.get_args(args)

    return (name,l)

################################################################################
# EEE - Chat commands                                                          #
################################################################################

  @botcmd(name='redo')
  def __redo(self,mess,args):
    """redo last command - redo [args]"""
  
    # this is a dummy function so it gets displayed in the help command
    # the real logic is at the end of callback_message()
    return

  @botcmd(name='last')
  def __last(self,mess,args):
    """display last command (from any chat)"""

    return self.last_cmd.get(mess.get_from().get_base(),'No past commands')

  @botcmd(name='git')
  def __git(self,mess,args):
    """return a link to the github page"""

    return 'https://github.com/TheSchwa/sibyl'

  @botcmd(name='about')
  def __about(self,mess,args):
    """print version and some plug-in info"""

    cmds = len(self.hooks['chat'])
    funcs = self.hooks['chat'].values()
    plugins = sorted(self.plugins+['sibylbot'])
    return ('SibylBot %s (%s) --- %s commands from %s plugins: %s' %
        (__version__,self.opt('chat_proto')[0],cmds,len(plugins),plugins))

  @botcmd(name='hello')
  def __hello(self,mess,args):
    """reply if someone says hello"""

    return 'Hello world!'

  @botcmd(name='help')
  def __help(self,mess,args):
    """return help info about cmds - help [cmd]"""
    if not args:
      if self.__doc__:
        description = self.__doc__.strip()
      else:
        description = 'Available commands:'

      usage = '\n'.join(sorted([
        '%s: %s' % (name, (command.__doc__ or \
          '(undocumented)').strip().split('\n', 1)[0])
        for (name, command) in self.hooks['chat'].iteritems() \
          if not command._sibylbot_dec_chat_hidden
      ]))
      usage = '\n\n' + '\n\n'.join(filter(None,
        [usage, self.MSG_HELP_TAIL % {'helpcommand': 'help'}]))
    else:
      description = ''
      args = self.__remove_prefix(args[0])
      if args in self.hooks['chat']:
        usage = (self.hooks['chat'][args].__doc__ or \
          'undocumented').strip()
      else:
        usage = self.MSG_HELP_UNDEFINED_COMMAND

    top = self.__top_of_help_message()
    bottom = self.__bottom_of_help_message()
    return ''.join(filter(None, [top, description, usage, bottom]))

################################################################################
# FFF - UI Functions                                                           #
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
# GGG - Run and Stop Functions                                                 #
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

  def __log_connect_msg(self,rooms=None):
    """log a message to appear when the bot connects"""

    self.log.info('')
    self.log.info('SibylBot connecting...')
    self.log.info('')
    self.log.info('Chat : %s' % self.opt('chat_proto')[0])
    self.log.info('User : %s' % self.opt('username'))
    if rooms:
      for room in rooms:
        self.log.info('Room : %s/%s' %
            (room['room'],(room['nick'] if room['nick'] else 'Sibyl')))
    else:
      self.log.info('Room : None')
    self.log.info('Plug : %s' % ','.join(self.plugins))
    self.log.info('Cmds : %i' % len(self.hooks['chat']))
    self.log.info('Log  : %s' %
        logging.getLevelName(self.log.getEffectiveLevel()))
    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')

  def __serve_forever(self):
    """process loop - connect and process messages"""

    # if we're not connected, try to connect
    # protocol.connected should raise ConnectFailure if it doesn't work
    if not self.protocol.is_connected():
      self.protocol.connect()

    # sanity check just in case the protocol isn't implemented correctly
    if not self.protocol.is_connected():
      raise ConnectFailure

    self.log.info('bot connected; serving forever')
    for room in self.opt('rooms'):
      self.protocol.join_room(room['room'],room['nick'],room['pass'])

    self.__run_hooks('con')

    # process messages forever unless self.quit()
    while not self.__finished:
      try:
        self.__idle_proc()
        self.protocol.process()
      except KeyboardInterrupt as e:
        self.quit('stopped by keyboard interrupt')

  def __run_forever(self):
    """reconnect loop - catch known exceptions"""

    # try to reconnect forever unless self.quit()
    while not self.__finished:
      try:
        self.__serve_forever()
        
      except (PingTimeout,ConnectFailure,ServerShutdown) as e:
        self.protocol.disconnected()
        self.__run_hooks('discon',e)
        
        # attempt to reconnect if self.catch_except
        if self.opt('catch_except'):
          reason = {PingTimeout:'ping timeout',
                    ConnectFailure:'unable to connect',
                    ServerShutdown:'server shutdown'}
          self.log.error('Connection lost ('+reason[e.__class__]+
              '); retrying in '+str(self.opt('recon_wait'))+' sec')

        # traceback all exceptions and quit if not self.catch_except
        else:
          raise e

        # wait then reconnect
        time.sleep(self.opt('recon_wait'))
        self.__run_hooks('recon')

################################################################################
# HHH - User-facing functions                                                  #
################################################################################

  def run_forever(self):
    """run the bot catching any unhandled exceptions"""

    # unfortunately xmpppy has a couple print statements, so kill stdout
    stdout = sys.stdout
    sys.stdout = open(os.devnull,'wb')

    self.__log_connect_msg(rooms=self.opt('rooms'))

    # catch unhandled Exceptions and write traceback to the log
    try:
      self.__run_forever()
    except Exception as e:
      self.log.critical('UNHANDLED: %s\n\n%s' %
          (e.__class__.__name__,traceback.format_exc(e)))
      self.log.critical(self.MSG_UNHANDLED)

    # shutdown cleanly
    self.protocol.shutdown()
    self.__run_hooks('down')

  # @param msg (str) [None] message to log
  def quit(self,msg=None):
    """Stop serving messages and exit"""
    
    self.__finished = True
    if msg:
      self.log.critical(msg)
    else:
      self.log.critical('SibylBot.quit() called, but no reason given')

  # @param name (str) [None] name of the opt to fetch
  # @return (object) the value of the opt or the entire opt dict if no name
  def opt(self,name=None):
    """return the value of the specified config option"""

    if not name:
      return self.conf.opts
    return self.conf.opts[name]

  # @param name (str) name of the instance variable to set
  # @param val (object) [None] value to set
  # @raise (AttributeError) if the var already exists
  def add_var(self,name,val=None):
    """add a var to the bot, or raise an exception if it already exists"""

    caller = util.get_caller()
    if hasattr(self,name):
      space = self.ns_opt.get(name,'sibylbot')
      self.log.critical('plugin "%s" tried to overwrite var "%s" from "%s"' %
          (caller,name,space))
      raise DuplicateVarError

    setattr(self,name,val)
    self.ns_opt[name] = caller

  # @param cmd (str) name of chat cmd to run
  # @param args (list) [None] arguments to pass to the command
  # @param mess (Message) [None] message to pass to the command
  # @return (str,None) the result of the command
  def run_cmd(self,cmd,args=None,mess=None):
    """run a chat command manually"""

    # catch invalid arguments to help developers
    if (args is not None) and (not isinstance(args,list)):
      raise ValueError('The args to run_cmd must be list')

    if args is None:
      args = []
    return self.hooks['chat'][cmd](mess,args)

  # @param plugin (str) [None] name of plugin to check for, or return all
  # @return (bool,list) True if the plugin was loaded, or list all
  def has_plugin(self,plugin=None):
    """check if a plugin was loaded"""

    if not plugin:
      return self.plugins
    return (plugin in self.plugins)
