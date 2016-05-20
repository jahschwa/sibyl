#!/usr/bin/env python
#
# XBMC JSON-RPC XMPP MUC bot

# built-ins
import sys,logging,re,os,imp,inspect,traceback

# in-project
from config import Config
from protocol import Message
from protocol import PingTimeout,ConnectFailure,AuthFailure,ServerShutdown
from decorators import botcmd
import util

__author__ = 'Joshua Haas <haas.josh.a@gmail.com>'
__version__ = 'v6.0.0'
__website__ = 'https://github.com/TheSchwa/sibyl'
__license__ = 'GNU General Public License version 3 or later'

################################################################################
# SibylBot                                                                     #
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

  def __init__(self,conf_file='sibyl.conf'):
    """override to only answer direct msgs"""

    # load config
    self.conf_file = conf_file
    self.conf = Config(self)
    self.conf.reload()
    
    # load plugin config options
    files = [x for x in os.listdir(self.cmd_dir) if x.endswith('.py')]
    for f in files:
      f = f.split('.')[0]
      mod = util.load_module(f,self.cmd_dir)
      self.__load_conf(mod)

    # try to load chat protocol config options
    if self.chat_proto:
      mod = util.load_module('sibyl_'+self.chat_proto[0],'protocols')
      self.__load_conf(mod)

    # reload config after plugins
    self.conf.clear_log()
    result = self.conf.reload()

    # configure logging
    logging.basicConfig(filename=self.log_file,
        format='%(asctime).19s | %(name)-8.8s | %(levelname).3s | %(message)s',
        level=self.log_level)
    self.log = logging.getLogger('sibylbot')

    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')
    self.log.critical('SibylBot starting...')
    self.log.info('')
    self.log.info('Conf : '+os.path.abspath(self.conf_file))
    self.log.info('PID  : %s' % os.getpid())
    self.log.info('')
    self.log.info('Reading config file "%s"...' % self.conf_file)

    # log config errors and check for success
    self.conf.process_log()
    if result==Config.FAIL:
      self.log.critical('Error parsing config file; exiting')
    elif result==Config.ERRORS:
      self.log.warning('Parsed config file with warnings')
      self.log.info('')
    
    if result==Config.FAIL:
      print '\n   *** Fatal error: unusable config file (see log) ***\n'
      print '   Config file: %s' % os.path.abspath(self.conf_file)
      print '   Log file:    %s\n' % os.path.abspath(self.log_file)
      sys.exit(1)
    self.log.info('Success parsing config file')

    # create protocol object
    self.protocol = self.chat_proto[1](
        self,logging.getLogger(self.chat_proto[0]))

    # used to stop the bot cleanly
    self.__finished = False

    # init redo command
    self.last_cmd = {}

    # dict to keep track of room joining results
    self.muc_pending = {}

    # Load hooks from self.cmd_dir
    self.hooks = {x:{} for x in
        ['chat','init','mucs','mucf','msg','priv','group','status','idle']}
    self.__load_funcs(self,'sibylbot',silent=True)
    self.__load_plugins(self.cmd_dir)

    # Run plug-in init hooks
    self.__run_hooks('init')

################################################################################
# Plug-in framework                                                            #
################################################################################

  def __load_plugins(self,d):
    """recursively load all plugins from all sub-directories"""

    files = [x for x in os.listdir(d) if x.endswith('.py')]    
    for f in files:
      f = f.split('.')[0]
      mod = self.__load_module(f,d)
      self.__load_funcs(mod,f)

    dirs = [os.path.join(d,x) for x in os.listdir(d) if os.path.isdir(os.path.join(d,x))]
    for x in dirs:
      self.__load_plugins(x)

  def __load_funcs(self,mod,fil,silent=False):
    
    for (name,func) in inspect.getmembers(mod,inspect.isroutine):
      
      if getattr(func,'_sibylbot_dec_func',False):
        setattr(self,name,self.__bind(func))
        if not silent:
          self.log.debug('Registered function: %s.%s' % (fil,name))

      for (hook,dic) in self.hooks.items():
        if getattr(func,'_sibylbot_dec_'+hook,False):
          fname = getattr(func,'_sibylbot_dec_'+hook+'_name',None)
          s = 'Registered %s command: %s.%s = %s' % (hook,fil,name,fname)
          if fname is None:
            fname = fil+'.'+name
            s = 'Registered %s hook: %s.%s' % (hook,fil,name)
          dic[fname] = self.__bind(func)
          if not silent:
            self.log.debug(s)

  def __load_conf(self,mod):

    for (name,func) in inspect.getmembers(mod,inspect.isfunction):
      if getattr(func,'_sibylbot_dec_conf',False):
        opts = func(self)
        if not isinstance(opts,list):
          opts = [opts]
        self.conf.add_opts(opts)

  def __load_module(self,name,path):

    found = imp.find_module(name,[path])
    try:
      return imp.load_module(name,*found)
    finally:
      found[0].close()

  def __bind(self,func):

    return func.__get__(self,SibylBot)

  def __run_hooks(self,hook,*args):
    
    for (name,func) in self.hooks[hook].items():
      if hook!='idle':
        self.log.debug('Running %s hook: %s' % (hook,name))
      func(*args)

  def __idle_proc(self):
    """This function will be called in the main loop."""

    self.__run_hooks('idle')

  def run_cmd(self,cmd,args=None,mess=None):
    """run a chat command manually"""

    if (args is not None) and (not isinstance(args,list)):
      raise ValueError('The args to run_cmd must be list')

    if args is None:
      args = []
    return self.hooks['chat'][cmd](mess,args)

################################################################################
# Callbacks for Protocols                                                      #
################################################################################

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

    # Execute status hooks and return
    if typ==Message.STATUS:
      self.__run_hooks('status',mess)
      return
    
    cmd = self.get_cmd(mess)

    # Execute hooks, return if ERROR
    if typ==Message.PRIVATE:
      self.__run_hooks('priv',mess,cmd)
      self.__run_hooks('msg',mess,cmd)
    elif typ==Message.GROUP:
      self.__run_hooks('group',mess,cmd)
      self.__run_hooks('msg',mess,cmd)
    elif typ==Message.ERROR:
      self.__run_hooks('err',mess,cmd)
      return
    else:
      self.log.error('Unknown message type "%s"' % typ)
      return

    # If cmd is None, the msg was not a cmd directed at us
    if not cmd:
      return
    
    # account for double cmd_prefix = redo (e.g. !!)
    if self.cmd_prefix and cmd.startswith(self.cmd_prefix):
      new = self.remove_prefix(cmd)
      cmd = 'redo'
      if len(new.strip())>0:
        cmd += (' '+new.strip())

    (cmd_name,args) = self.get_args(cmd)

    # check if the command exists
    if cmd_name not in self.hooks['chat']:
      self.log.info('Unknown command "%s"' % cmd_name)
      if typ==Message.GROUP:
        default_reply = None
      else:
        default_reply = self.MSG_UNKNOWN_COMMAND % {
          'command': cmd,
          'helpcommand': 'help',
        }
      reply = self.unknown_command(mess,cmd_name,args)
      if reply is None:
        reply = default_reply
      if reply:
        self.protocol.send(reply,frm)
      return
    
    # check against bw_list
    for rule in self.bw_list:
      if (rule[1]!='*') and (rule[1] not in real):
        continue
      if rule[2]!='*' and rule[2]!=cmd_name:
        continue
      applied = rule

    if applied[0]=='b':
      self.protocol.send('You do not have permission to execute that command',frm)
      return

    # redo command logic
    if cmd_name=='redo':
      self.log.debug('Redo cmd; original msg: "'+text+'"')
      cmd = self.last_cmd.get(usr,'echo Nothing to redo')
      if len(args)>1:
        cmd += (' '+' '.join(args[1:]))
        self.last_cmd[usr] = cmd
      (cmd_name,args) = self.get_args(cmd)
    elif cmd_name!='last':
      self.last_cmd[usr] = cmd

    # log command and message info
    self.log.info('*** cmd  = %s' % cmd_name)
    self.log.debug('*** from = %s' % frm)
    if real!=frm:
      self.log.debug('*** real = %s' % real)
    self.log.debug('*** type = %s' % Message.type_to_str(typ))
    self.log.debug('*** text = %s' % text)
    self.log.debug('*** b/w  = %s' % str(applied))

    # execute the command
    try:
      reply = self.hooks['chat'][cmd_name](mess,args)
    except Exception, e:
      self.log.exception('An error happened while processing '\
        'a message ("%s") from %s: %s"' %
        (text,frm,traceback.format_exc(e)))
      reply = self.MSG_ERROR_OCCURRED
      if self.except_reply:
        reply = traceback.format_exc(e).split('\n')[-2]
    if reply:
      self.protocol.send(reply,frm)

  def _cb_join_room_success(self,room):
    """execute callbacks on successfull MUC join"""
    
    self.__run_hooks('mucs',room)

  def _cb_join_room_failure(self,room,error):
    """execute callbacks on successfull MUC join"""
    
    self.__run_hooks('mucf',room,error)

################################################################################
# Helper functions                                                             #
################################################################################

  def get_cmd(self,mess):
    """return the body of mess with nick and prefix removed, or None if invalid"""

    text = mess.get_text()
    frm = mess.get_from()

    direct = False
    prefix = False

    # only direct logic
    room = frm.get_room()
    if self.protocol.in_room(room) and text.lower().startswith(self.protocol.get_nick(room).lower()):
      text = ' '.join(text.split(' ',1)[1:])
      direct = True

    # command prefix logic
    text = self.remove_prefix(text)
    prefix = (text!=mess.get_text())

    if mess.get_type()==Message.PRIVATE:
      return text
    else:
      if ((not self.only_direct) and (not self.cmd_prefix) or
          ((self.only_direct and direct) or (self.cmd_prefix and prefix))):
        return text
    return None

  def remove_prefix(self,text):
    """remove the command prefix from the given text"""

    if not self.cmd_prefix:
      return text
    if not text.startswith(self.cmd_prefix):
      return text
    return text[len(self.cmd_prefix):]

  def get_args(self,cmd):
    """return the cmd_name and args in a tuple, accounting for quotes"""

    args = cmd.split(' ')
    name = args[0]
    args = ' '.join(args[1:]).strip()

    l = []
    if args:
      l = util.get_args(args)

    return (name,l)

################################################################################
# Commands                                                                     #
################################################################################

  @botcmd
  def redo(self,mess,args):
    """redo last command - redo [args]"""
  
    # this is a dummy function so it gets displayed in the help command
    # the real logic is at the end of callback_message()
    return

  @botcmd
  def last(self,mess,args):
    """display last command (from any chat)"""

    return self.last_cmd.get(mess.get_from().get_base(),'No past commands')

  @botcmd
  def git(self,mess,args):
    """return a link to the github page"""

    return 'https://github.com/TheSchwa/sibyl'

  @botcmd
  def hello(self,mess,args):
    """reply if someone says hello"""

    return 'Hello world!'

  @botcmd
  def help(self,mess,args):
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
      args = self.remove_prefix(args[0])
      if args in self.hooks['chat']:
        usage = (self.hooks['chat'][args].__doc__ or \
          'undocumented').strip()
      else:
        usage = self.MSG_HELP_UNDEFINED_COMMAND

    top = self.top_of_help_message()
    bottom = self.bottom_of_help_message()
    return ''.join(filter(None, [top, description, usage, bottom]))

################################################################################
# UI Functions                                                                 #
################################################################################

  def unknown_command(self, mess, cmd, args):
    """Default handler for unknown commands

    Override this method in derived class if you
    want to trap some unrecognized commands.  If
    'cmd' is handled, you must return some non-false
    value, else some helpful text will be sent back
    to the sender.
    """
    return None

  def top_of_help_message(self):
    """Returns a string that forms the top of the help message

    Override this method in derived class if you
    want to add additional help text at the
    beginning of the help message.
    """
    return ""

  def bottom_of_help_message(self):
    """Returns a string that forms the bottom of the help message

    Override this method in derived class if you
    want to add additional help text at the end
    of the help message.
    """
    return ""

################################################################################
# Run and Stop Functions                                                       #
################################################################################

  def quit(self,msg=None):
    """Stop serving messages and exit.

    I find it is handy for development to run the
    jabberbot in a 'while true' loop in the shell, so
    whenever I make a code change to the bot, I send
    the 'reload' command, which I have mapped to call
    self.quit(), and my shell script relaunches the
    new version.
    """
    self.__finished = True
    if msg:
      self.log.critical(msg)

  def shutdown(self):
    """This function will be called when we're done serving

    Override this method in derived class if you
    want to do anything special at shutdown.
    """
    pass

  def __serve_forever(self, connect_callback=None, disconnect_callback=None):
    """Connects to the server and handles messages."""
    self.protocol.connect(self.username,self.password)
    if self.protocol.is_connected():
      self.log.info('bot connected; serving forever')
    else:
      self.log.critical('could not connect to server - aborting.')
      return

    if connect_callback:
      connect_callback()

    while not self.__finished:
      try:
        self.protocol.process()
        self.__idle_proc()
      except KeyboardInterrupt:
        self.log.critical('stopped by keyboard interrupt')
        break

    self.shutdown()

    if disconnect_callback:
      disconnect_callback()

  def log_startup_msg(self,rooms=None):
    """log a message to appear when the bot connects"""

    self.log.info('')
    self.log.critical('SibylBot connecting...')
    self.log.info('')
    self.log.info('Chat : %s' % self.protocol.get_name())
    self.log.info('User : %s' % self.username)
    if rooms:
      for room in rooms:
        self.log.info('Room : %s/%s' %
            (room['room'],(room['nick'] if room['nick'] else 'Sibyl')))
    else:
      self.log.info('Room : None')
    self.log.info('Cmds : %i' % len(self.hooks['chat']))
    self.log.info('Log  : %s' % logging.getLevelName(self.log.getEffectiveLevel()))
    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')

  def run_forever(self,
        connect_callback=None, disconnect_callback=None):
    """join rooms (optional), serve forever, reconnect if needed"""

    self.log_startup_msg(rooms=self.rooms)

    # log unknown exceptions then quit
    try:
      while not self.protocol.is_connected():
        try:
          if len(self.rooms):
            for room in self.rooms:
              self.protocol.join_room(room['room'],room['nick'],room['pass'])
          self.__serve_forever(connect_callback, disconnect_callback)
        
        # catch known exceptions
        except (PingTimeout,ConnectFailure,ServerShutdown) as e:

          # attempt to reconnect if self.catch_except
          if self.catch_except:
            reason = {PingTimeout:'ping timeout',
                      ConnectFailure:'unable to connect',
                      ServerShutdown:'server shutdown'}
            self.log.error('Connection lost ('+reason[e.__class__]+'); retrying in '+str(self.__reconnect_wait)+' sec')

          # traceback all exceptions and quit if not self.catch_except
          else:
            raise e

          # wait then reconnect
          time.sleep(self.recon_wait)
          self.protocol.disconnect()
          for room in self.get_rooms(in_only=True):
            self.part_room(room)

    # catch all exceptions, add to log, then quit
    except Exception as e:
      self.log.critical('CRITICAL: %s\n\n%s' % (e.__class__.__name__,traceback.format_exc(e)))
      self.shutdown()
