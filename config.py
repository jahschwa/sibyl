#!/usr/bin/env python

import time,os,socket,copy,logging
from collections import OrderedDict as odict
import ConfigParser as cp

import util

DUMMY = 'dummy'

################################################################################
# Config class                                                                 #
################################################################################

class Config(object):

  DEF = 0
  REQ = 1
  VALID = 2
  PARSE = 3

  FAIL = 0
  SUCCESS = 1
  ERRORS = 2

  def __init__(self,bot):
    """create a new config parser tied to the given bot"""

    self.OPTS = odict([

#option          default             requir  validate_func     parse_func
#-------------------------------------------------------------------------------
('username',    (None,               True,   None,             None)),
('password',    (None,               True,   None,             None)),
('nick_name',   ('Sibyl',            False,  None,             None)),
('log_level',   (logging.INFO,       False,  None,             self.parse_log)),
('log_file',    ('sibyl.log',        False,  self.valid_file,  None)),
('bw_list',     ([('w','*','*')],    False,  self.valid_bw,    self.parse_bw)),
('chat_ctrl',   (False,              False,  None,             self.parse_bool)),
('link_echo',   (False,              False,  None,             self.parse_bool)),

#jabberbot options
#-------------------------------------------------------------------------------
('resource',    (None,               False,  None,             None)),
('debug',       (False,              False,  None,             self.parse_bool)),
('rooms',       ([],                 False,  None,             self.parse_room)),
('priv_domain', (True,               False,  None,             self.parse_bool)),
('cmd_dir',     ('cmds',             False,  self.valid_dir,   None)),
('cmd_prefix',  (None,               False,  None,             None)),
('port',        (5222,               False,  None,             self.parse_int)),
('ping_freq',   (0,                  False,  None,             self.parse_int)),
('except_reply',(False,              False,  None,             self.parse_bool)),
('ping_timeout',(3,                  False,  None,             self.parse_int)),
('only_direct', (True,               False,  None,             self.parse_bool)),
('recon_wait',  (60,                 False,  None,             self.parse_int)),
('catch_except',(True,               False,  None,             self.parse_bool))

    ])
    
    self.opts = None
    self.bot = bot
    self.conf_file = bot.conf_file
    util.can_write_file(self.conf_file,delete=True)
    if not os.path.isfile(self.conf_file):
      self.write_default_conf()
    self.log_msgs = []

  def __bind(self,func):

    return func.__get__(self,Config)

  def get_default(self):
    """return a dict of defaults in the form {opt:value}"""

    return odict([(opt,value[self.DEF]) for (opt,value) in self.OPTS.iteritems()])

  def add_opts(self,opts):
    """add several new options"""

    for opt in opts:
      self.add_opt(opt)

  def add_opt(self,opt):
    """add the option to our dictionary for parsing"""

    name = opt['name']
    default = opt.get('default',None)
    req = opt.get('req',False)
    valid = opt.get('valid',None)
    if valid:
      valid = self.__bind(valid)
    parse = opt.get('parse',None)
    if parse:
      parse = self.__bind(parse)
    
    self.OPTS[name] = (default,req,valid,parse)
    
  def reload(self):
    """load opts from config file into bot"""

    try:
      self.__update()

      errors = []
      for opt in self.opts:
        if self.OPTS[opt][self.REQ] and not self.opts[opt]:
          self.log('critical','Missing required option "%s"' % opt)
          errors.append(opt)
      if len(errors):
        raise ValueError('Missing required options %s' % errors)
      
      self.__load()

      warnings = [x for x in self.log_msgs if x[0]>=logging.WARNING]
      if len(warnings):
        return self.ERRORS
      else:
        return self.SUCCESS
      
    except:
      self.bot.log_file = self.OPTS['log_file'][self.DEF]
      self.bot.log_level = self.OPTS['log_level'][self.DEF]
      return self.FAIL

  def __update(self):
    """update self.opts from config file"""

    self.opts = self.get_default()
    opts = self.__read()
    self.__parse(opts)
    self.__validate(opts)
    self.opts.update(opts)

  def __read(self):
    """return a dict representing config file in the form {opt:value}"""

    config = cp.SafeConfigParser()
    try:
      result = config.readfp(FakeSecHead(open(self.conf_file)))
    except:
      self.log('critical','Error parsing config file')
      raise IOError
    
    secs = config.sections()
    for sec in secs:
      if sec!=DUMMY:
        self.log('info','Ignoring section "%s" in config file' % sec)
    
    items = config.items(DUMMY)
    return {x:y for (x,y) in items}

  def __parse(self,opts):
    """parse the opt value strings into objects using their parse function"""

    for opt in opts.keys():
      if opt not in self.OPTS:
        self.log('info','Unknown config option "%s"' % opt)
        del opts[opt]
      else:
        func = self.OPTS[opt][self.PARSE]
        if func:
          try:
            opts[opt] = func(opt,opts[opt])
          except Exception as e:
            self.log('warning','Error parsing "%s"; using default' % opt)
            del opts[opt]

  def __validate(self,opts):
    """delete opts that fail their validation function"""

    for opt in opts.keys():
      func = self.OPTS[opt][self.VALID]
      if func and not func(opts[opt]):
        self.log('warning','Invalid value for config option "%s"' % opt)
        del opts[opt]

  def __load(self):
    """take everything in self.opts and add them as attributes to our bot"""
    
    for opt in self.opts:
      self.bot.__setattr__(opt,self.opts[opt])

  def write_default_conf(self):
    """write a default, completely commented-out config file"""

    s = ''
    for (opt,val) in self.get_default().iteritems():
      s += ('#%s = %s\n' % (opt,val))
    with open(self.conf_file,'w') as f:
      f.write(s)

################################################################################
# Validate functions                                                           #
################################################################################

  def valid_ip(self,s):
    """return True if s is a valid ip"""

    try:
      socket.inet_aton(s)
      return True
    except:
      return False

  def valid_file(self,s):
    """return True if we can write to the file"""

    try:
      util.can_write_file(s,delete=True)
      return True
    except:
      return False

  def valid_bw(self,bw):
    """return True if the bw list is valid"""

    for (color,_,_) in bw:
      if color not in ('b','w'):
        self.log('warning','Invalid color "%s" in "bw_list"' % color)
        return False
    return True

  def valid_dir(self,cmd):
    """return True if the directory exists"""

    try:
      os.listdir(os.path.abspath(cmd))
      return True
    except:
      return False

################################################################################
# Parse functions                                                              #
################################################################################

  def parse_room(self,opt,val):
    """parse the rooms into a list"""

    val = val.replace('\n','')
    entries = util.split_strip(val,';')
    rooms = []
    for entry in entries:
      if entry=='':
        continue
      params = util.split_strip(entry,',')
      if not params[0]:
        raise ValueError
      room = {'room':params[0],'nick':None,'pass':None}
      if len(params)>1 and params[1]:
        room['nick'] = params[1]
      if len(params)>2 and params[2]:
        room['pass'] = params[2]
      rooms.append(room)
    return rooms

  def parse_log(self,opt,val):
    """parse the specified log level"""

    levels = {'critical' : logging.CRITICAL,
              'error'    : logging.ERROR,
              'warning'  : logging.WARNING,
              'info'     : logging.INFO,
              'debug'    : logging.DEBUG}
    
    return levels[val]

  def parse_bw(self,opt,val):
    """parse and fully expand the bw_list"""

    val = val.replace('\n','')
    entries = util.split_strip(val,';')
    bw = copy.copy(self.OPTS[opt][self.DEF])
    for entry in entries:
      if entry=='':
        continue
      (color,users,cmds) = util.split_strip(entry)
      users = util.split_strip(users,',')
      cmds = util.split_strip(cmds,',')
      for user in users:
        for cmd in cmds:
          bw.append((color,user,cmd))
    return bw

  def parse_bool(self,opt,val):
    """return a bool"""

    if val.strip().lower()=='true':
      return True
    if val.strip().lower()=='false':
      return False
    raise ValueError

  def parse_int(self,opt,val):
    """return an int"""

    return int(val)

################################################################################
# Logging                                                                      #
################################################################################

  def log(self,lvl,msg):
    """add the message to the queue"""

    self.log_msgs.append((lvl,msg))

  def process_log(self):
    """can only be called after bot.log has been initialised"""

    for (lvl,msg) in self.log_msgs:
      lvl = self.parse_log(None,lvl)
      self.bot.log.log(lvl,msg)
    self.clear_log()

  def clear_log(self):
    """clear the log"""
    
    self.log_msgs = []

################################################################################
# FakeSecHead class                                                            #
################################################################################

class FakeSecHead(object):
    def __init__(self, fp):
        self.fp = fp
        self.sechead = '[%s]\n' % DUMMY
    def readline(self):
        if self.sechead:
            try: 
                return self.sechead
            finally: 
                self.sechead = None
        else: 
            return self.fp.readline()
