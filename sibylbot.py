#!/usr/bin/env python
#
# XBMC JSON-RPC XMPP MUC bot

# built-ins
import sys,logging,re,os,imp,inspect

# in-project
from jabberbot import JabberBot,botcmd
from config import Config
import util

################################################################################
# Decorators                                                                   #
################################################################################

def botconf(func):
  """Decorator for bot helper functions"""

  setattr(func, '_sibylbot_dec_conf', True)
  return func

################################################################################
# SibylBot                                                                     #
################################################################################

class SibylBot(JabberBot):
  """More details: https://github.com/TheSchwa/sibyl/wiki/Commands"""

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
      for (name,func) in inspect.getmembers(mod,inspect.isfunction):
        if getattr(func,'_sibylbot_dec_conf',False):
          opts = func(self)
          if not isinstance(opts,list):
            opts = [opts]
          self.conf.add_opts(opts)

    # reload config after plugins
    self.conf.clear_log()
    result = self.conf.reload()

    # configure logging
    logging.basicConfig(filename=self.log_file,format='%(asctime).19s | %(levelname).3s | %(message)s',level=self.log_level)
    self.log = logging.getLogger()

    self.log.info('')
    self.log.info('-'*50)
    self.log.info('')
    self.log.critical('SibylBot starting...')
    self.log.info('')
    self.log.critical('Reading config file "%s"...' % self.conf_file)

    if result==Config.FAIL:
      self.log.critical('Unable to parse config file; exiting')
    elif result==Config.ERRORS:
      self.log.critical('Parsed config file with warnings')
      self.log.info('')
    
    # log config errors and check for success
    self.conf.process_log()
    if result==Config.FAIL:
      sys.exit(1)
    self.log.info('Success parsing config file')

    # call JabberBot init
    super(SibylBot,self).__init__(self.username,self.password,
        res = self.resource,
        debug = self.debug,
        rooms = self.rooms,
        privatedomain = self.priv_domain,
        cmd_dir = self.cmd_dir,
        cmd_prefix = self.cmd_prefix,
        port = self.port,
        ping_freq = self.ping_freq,
        ping_timeout = self.ping_timeout,
        only_direct = self.only_direct,
        reconnect_wait = self.recon_wait,
        catch_except = self.catch_except)

    # init redo command
    self.last_cmd = {}

    # variable to retain MUC JID for certain command purposes
    self.last_jid = None

    # dict to keep track of room joining results
    self.muc_pending = {}

  def callback_message(self,conn,mess):
    """override to look at realjids and implement bwlist and redo"""

    frm = mess.getFrom()
    usr = str(frm)
    msg = mess.getBody()

    cmd = self.get_cmd(mess)

    self.last_jid = usr
    # convert MUC JIDs to real JIDs
    if (mess.getType()=='groupchat') and (usr in self.real_jids):
      usr = self.real_jids[usr]

    if cmd:

      # account for double cmd_prefix = redo (e.g. !!)
      if self.cmd_prefix and cmd.startswith(self.cmd_prefix):
        new = self.remove_prefix(cmd)
        cmd = 'redo'
        if len(new.strip())>0:
          cmd += (' '+new.strip())

      args = cmd.split(' ')
      cmd_name = args[0]
      
      # check against bw_list
      for rule in self.bw_list:
        if (rule[1]!='*') and (rule[1] not in usr):
          continue
        if rule[2]!='*' and rule[2]!=cmd_name:
          continue
        applied = rule

      if applied[0]=='w':
        self.log.debug('Allowed "'+usr+'" to execute "'+cmd_name+'" with rule '+str(applied))
      else:
        self.log.debug('Denied "'+usr+'" from executing "'+cmd_name+'" with rule '+str(applied))
        self.send_simple_reply(mess,'You do not have permission to execute that command')
        return

      # redo command logic
      if cmd_name=='redo':
        self.log.debug('Redo cmd; original msg: "'+msg+'"')
        cmd = self.last_cmd.get(frm.getStripped(),'echo Nothing to redo')
        if len(args)>1:
          cmd += (' '+' '.join(args[1:]))
          self.last_cmd = cmd
        if mess.getType()=='groupchat':
          room = frm.getStripped()
          nick = self.mucs[room]['nick']
          if self.only_direct and not cmd.startswith(nick):
            cmd = (nick+' '+cmd)
        mess.setBody(cmd)
      else:
        self.last_cmd[frm.getStripped()] = cmd

    return super(SibylBot,self).callback_message(conn,mess)

################################################################################
# Commands                                                                     #
################################################################################

  @botcmd
  def redo(bot,mess,args):
    """redo last command - redo [args]"""
  
    # this is a dummy function so it gets displayed in the help command
    # the real logic is at the end of callback_message()
    return

  @botcmd
  def git(bot,mess,args):
    """return a link to the github page"""

    return 'https://github.com/TheSchwa/sibyl'

  @botcmd
  def hello(bot,mess,args):
    """reply if someone says hello"""

    return 'Hello world!'
