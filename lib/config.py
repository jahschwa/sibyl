#!/usr/bin/python
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

import time,os,socket,copy,logging,inspect,traceback
from collections import OrderedDict as odict
import ConfigParser as cp

from sibyl.lib.protocol import Protocol
import sibyl.lib.util as util
from sibyl.lib.password import Password

DUMMY = 'dummy'

class DuplicateOptError(Exception):
  pass

################################################################################
# Config class
################################################################################

class Config(object):

  # indices in option tuple for convenience
  DEF = 0
  REQ = 1
  PARSE = 2
  VALID = 3
  POST = 4

  # config reload results
  FAIL = 0
  SUCCESS = 1
  ERRORS = 2
  DUPLICATES = 3

  def __init__(self,conf_file):
    """create a new config parser tied to the given bot"""

    # OrderedDict containing full descriptions of options
    self.OPTS = odict([

#option         default               requir  parse_func            validate_func       post_func
#------------------------------------------------------------------------------------------------
('protocols',   ({},                  True,   self.parse_protocols, None,               None)),
('enable',      ([],                  False,  self.parse_plugins,   None,               None)),
('disable',     ([],                  False,  self.parse_plugins,   None,               None)),
('rename',      ({},                  False,  self.parse_rename,    None,               None)),
('cmd_dir',     ('cmds',              False,  None,                 self.valid_dir,     None)),
('rooms',       ({},                  False,  self.parse_rooms,     None,               self.post_rooms)),
('nick_name',   ('Sibyl',             False,  None,                 None,               None)),
('log_level',   (logging.INFO,        False,  self.parse_log,       None,               None)),
('log_file',    ('data/sibyl.log',    False,  None,                 self.valid_wfile,   None)),
('log_append',  (True,                False,  self.parse_bool,      None,               None)),
('log_hooks',   (False,               False,  self.parse_bool,      None,               None)),
('log_requests',(False,               False,  self.parse_bool,      None,               None)),
('log_urllib3', (False,               False,  self.parse_bool,      None,               None)),
('bw_list',     ([('w','*','*')],     False,  self.parse_bw,        None,               None)),
('chat_ctrl',   (False,               False,  self.parse_bool,      None,               None)),
('cmd_prefix',  (None,                False,  None,                 None,               None)),
('except_reply',(False,               False,  self.parse_bool,      None,               None)),
('only_direct', (True,                False,  self.parse_bool,      None,               None)),
('catch_except',(True,                False,  self.parse_bool,      None,               None)),
('help_plugin', (False,               False,  self.parse_bool,      None,               None)),
('recon_wait',  (60,                  False,  self.parse_int,       None,               None)),
('kill_stdout', (True,                False,  self.parse_bool,      None,               None)),
('tell_errors', (True,                False,  self.parse_bool,      None,               None)),
('admin_protos',(['cli'],             False,  self.parse_admin,     self.valid_admin,   None)),
('persistence', (True,                False,  self.parse_bool,      None,               None)),
('state_file',  ('data/state.pickle', False,  None,                 self.valid_wfile,   None)),
('idle_time',   (0.1,                 False,  self.parse_float,     self.valid_nump,    None)),
('idle_count',  (5,                   False,  self.parse_int,       self.valid_nump,    None)),
('idle_freq',   (1,                   False,  self.parse_int,       self.valid_nump,    None)),
('defer_total', (100,                 False,  self.parse_int,       None,               None)),
('defer_proto', (100,                 False,  self.parse_int,       None,               None)),
('defer_room',  (10,                  False,  self.parse_int,       None,               None)),
('defer_priv',  (10,                  False,  self.parse_int,       None,               None))

    ])

    # create "namespace" dict
    self.NS = {k:'sibylbot' for k in self.OPTS}

    # initialise variables
    self.opts = None
    self.conf_file = conf_file
    self.log_msgs = []
    self.logging = True
    self.real_time = False
    self.__log = logging.getLogger('config')

    # raise an exception if we can't write to conf_file
    util.can_write_file(self.conf_file,delete=True)

    # write a default conf_file if it doesn't exist at all
    if not os.path.isfile(self.conf_file):
      self.write_default_conf()

  # @return (OrderedDict) defaults {option:value}
  def get_default(self):
    """return a dict of defaults in the form {opt:value}"""

    # populate a dictionary with the default values for all options
    opts = self.OPTS.iteritems()
    return odict([(opt,value[self.DEF]) for (opt,value) in opts])

  # @param opts (list of dict) options to add to defaults
  # @param ns (str) the namespace (e.g. filename) of the option
  # @return (bool) True if all opts added successfully
  def add_opts(self,opts,ns):
    """add several new options, catching exceptions"""

    success = True
    for opt in opts:
      try:
        self.add_opt(opt,ns)
      except DuplicateOptError:
        success = False

    return success

  # @param opt (dict) option to add to defaults
  # @param ns (str) the namespace (e.g. filename) of the option
  # @raise (DuplicateOptError) if the opt already exists
  #
  # See @botconf in https://github.com/TheSchwa/sibyl/wiki/Plug-Ins
  def add_opt(self,opt,ns):
    """add the option to our dictionary for parsing, log errors"""

    # construct option tuple and add to self.OPTS
    name = opt['name']

    if name in self.OPTS:
      self.log('critical','Duplicate opt "%s" from "%s" and "%s"' %
          (name,self.NS[name],ns))
      raise DuplicateOptError

    opt['default'] = opt.get('default',None)
    opt['req'] = opt.get('req',False)

    for hook in ('parse','valid','post'):
      opt[hook] = opt.get(hook,None)
      if opt[hook]:
        opt[hook] = opt[hook]

    self.OPTS[name] = (
      opt['default'],opt['req'],opt['parse'],opt['valid'],opt['post'])
    self.NS[name] = ns

  # @param opt (str) the option to set
  # @param val (str) the value to set (will be parsed into a Python object)
  # @return (bool) True if the option was actually changed
  def set_opt(self,opt,val):
    """parse,validate,set an opt in the bot returning False on failure"""

    # try to parse if necessary
    try:
      func = self.OPTS[opt][self.PARSE]
      if func:
        val = func(self,opt,val)
    except:
      return False

    # validate if necessary
    func = self.OPTS[opt][self.VALID]
    if func:
      if not func(self,val):
        return False

    # try to post if necessary
    try:
      func = self.OPTS[opt][self.POST]
      if func:
        val = func(self,self.opts,opt,val)
    except:
      return False

    # set the option in ourself
    self.opts[opt] = val
    return True

  # @param opt (str) the option to set
  # @param val (str) the value to set (will be parsed into a Python object)
  # @return (bool) True if the option was actually changed and saved
  def save_opt(self,opt,val,msg=None):
    """call set_opt then save it to the config file"""

    # return if set_opt() fails
    if not self.set_opt(opt,val):
      return False

    # note the time of the change at the end of the line
    s = ('### MODIFIED: '+time.asctime())
    if msg:
      s += (' ('+msg+')')
    s += ('\n'+opt+' = '+val+'\n')
    with open(self.conf_file,'r') as f:
      lines = f.readlines()

    # search the config file for the specified opt to replace
    start = -1
    for (i,line) in enumerate(lines):
      line = line.strip()
      if line.startswith(opt):
        start = i
        break

    # if the opt was not active in the config file, simply add it to the end
    if start==-1:
      lines.append(s)

    # if the opt existed in the file
    else:

      # delete all non-comments until reaching next opt (account for multiline)
      del lines[start]
      n = start
      while (n<len(lines)):
        line = lines[n].strip()
        if self.__is_opt_line(line):
          break
        elif line.startswith('#') or line.startswith(';') or len(line)==0:
          n += 1
        else:
          del lines[n]
      lines.insert(start,s)

      # check for and delete an existing "### MODIFIED" line
      if start>0 and lines[start-1].startswith('### MODIFIED: '):
        del lines[start-1]

    with open(self.conf_file,'w') as f:
      f.writelines(lines)
    return True

  # @param opt (str) the name of the opt to reload
  def reload_opt(self,opt):
    """reload the specified opt from the config file"""

    old = self.real_time
    self.real_time = False
    self.reload(opt)
    msgs = [x for x in self.log_msgs[:] if 'Unknown config option' not in x[1]]
    self.clear_log()
    self.real_time = old
    return msgs

  # @param line (str) the line to check
  # @return (bool) True if the line contains an active (uncommented) option
  def __is_opt_line(self,line):
    """return True if this line contains an option"""

    line = line.strip()
    if line.startswith('#') or line.startswith(';'):
      return False

    set_char = line.find('=')
    com_char = line.find(' ;')
    if set_char==-1:
      return False
    if com_char==-1:
      return True
    return set_char<com_char

  # @param opt (None,str) [None] if specified, only reload the named opt
  # @param log (bool) [True] whether to log messages during the reload
  # @return (int) the result of the reload
  #   SUCCESS - no errors or warnings of any kind
  #   ERRORS  - ignored sections, ignore opts, parse fails, or validate fails
  #   FAIL    - missing any required opts
  def reload(self,opt=None,log=True):
    """load opts from config file and check for errors"""

    orig = self.logging
    self.logging = log
    errors = []

    # parse options from the config file and store them in self.opts
    try:
      self.__update(opt)
    except cp.InterpolationError as e:
      self.log('critical','Interpolation error; check for invalid % syntax')
    except Exception as e:
      self.log('critical','Unhandled exception parsing config file')
      full = traceback.format_exc(e)
      short = full.split('\n')[-2]
      self.log('error','  %s' % short)
      self.log('debug',full)

    # record missing required options
    for opt in self.opts:
      if self.OPTS[opt][self.REQ] and not self.opts[opt]:
        self.log('critical','Missing required option "%s"' % opt)
        errors.append(opt)

    self.logging = orig

    # return status
    if len(errors):
      return self.FAIL

    warnings = [x for x in self.log_msgs if x[0]>=logging.WARNING]
    if len(warnings):
      return self.ERRORS
    else:
      return self.SUCCESS

  def __update(self,opt=None):
    """update self.opts from config file"""

    # start with the defaults
    if not opt:
      self.opts = self.get_default()

    # get the values in the config file
    opts = self.__read()
    if opt:
      if opt in opts:
        opts = {opt:opts[opt]}
      else:
        opts = {}
    self.__parse(opts)
    self.__validate(opts)
    self.__post(opts)

    # update self.opts with parsed and valid values
    self.opts.update(opts)

  # @return (dict) the values of all config options read from the file
  def __read(self):
    """return a dict representing config file in the form {opt:value}"""

    # use a SafeConfigParser to read options from the config file
    config = cp.SafeConfigParser()
    try:
      config.readfp(FakeSecHead(open(self.conf_file)))
    except Exception as e:
      full = traceback.format_exc(e)
      short = full.split('\n')[-2]
      self.log('critical','Unable to read/parse config file')
      self.log('error','  %s' % short)
      self.log('debug',full)
      return {}

    # Sibyl config does not use sections; options in sections will be ignored
    secs = config.sections()
    for sec in secs:
      if sec!=DUMMY:
        self.log('error','Ignoring section "%s" in config file' % sec)

    # return a dictionary of all opts read from the config file
    items = config.items(DUMMY)
    return {x:y for (x,y) in items}

  # @param opts (dict) potential opt:value pairs to parse
  def __parse(self,opts):
    """parse the opt value strings into objects using their parse function"""

    for opt in opts.keys():

      # delete unrecognized options
      if opt not in self.OPTS:
        self.log('info','Unknown config option "%s"' % opt)
        del opts[opt]

      # parse recognized options and catch parsing exceptions
      else:
        func = self.OPTS[opt][self.PARSE]
        if func:
          try:
            opts[opt] = func(self,opt,opts[opt])
          except Exception as e:
            self.log('error','Error parsing "%s"; using default=%s' %
                (opt,self.opts[opt]))
            del opts[opt]

  # @param opts (dict) opt:value pairs to validate
  def __validate(self,opts):
    """delete opts that fail their validation function"""

    # delete invalid options
    for opt in opts.keys():
      func = self.OPTS[opt][self.VALID]
      if func and not func(self,opts[opt]):
        self.log('error','Invalid value for "%s"; using default=%s' %
            (opt,self.opts[opt]))
        del opts[opt]

  # @param opts (dict) opt:value pairs to run post triggers on
  def __post(self,opts):
    """allow opts to run code to check the values of other opts"""

    for opt in opts.keys():
      func = self.OPTS[opt][self.POST]
      if func:
        try:
          opts[opt] = func(self,opts,opt,opts[opt])
        except Exception as e:
          self.log('error','Error running post for "%s"; using default=%s' %
              (opt,self.opts[opt]))
          del opts[opt]

  def write_default_conf(self):
    """write a default, completely commented-out config file"""

    s = ''
    for (opt,val) in self.get_default().iteritems():
      s += ('#%s = %s\n' % (opt,val))
    with open(self.conf_file,'w') as f:
      f.write(s)

################################################################################
#
# Validate functions
#
# @param foo (object) the object to validate
# @return (bool) True if the object is acceptable
#
# When we call functions from plugins, we must pass "self" explicitly. However,
# the below functions are bound, and so pass "self" implicitly as well. If we
# called func(self,s) for one of the below functions, the function would
# actually receive func(self,self,s). The @staticmethod decorator fixes this.
#
################################################################################

  @staticmethod
  def valid_ip(self,s):
    """return True if s is a valid ip"""

    # account for port
    if ':' in s:
      s = s.split(':')
      if len(s)>2:
        return False
      if not s[1].isdigit():
        return False
      s = s[0]

    # use socket library to decide if the IP is valid
    try:
      socket.inet_aton(s)
      return True
    except:
      return False

  @staticmethod
  def valid_rfile(self,s):
    """return True if we can read the file"""

    try:
      with open(s,'r') as f:
        return True
    except:
      return False

  @staticmethod
  def valid_wfile(self,s):
    """return True if we can write to the file"""

    try:
      util.can_write_file(s,delete=True)
      return True
    except:
      return False

  @staticmethod
  def valid_dir(self,s):
    """return True if the directory exists"""

    try:
      os.listdir(os.path.abspath(s))
      return True
    except:
      return False

  @staticmethod
  def valid_admin(self,protos):
    """return True if every protocol in the list exists"""

    for proto in protos:
      fname = os.path.join('protocols','sibyl_'+proto+os.path.extsep+'py')
      if not os.path.isfile(fname):
        return False

    return True

  @staticmethod
  def valid_nump(self,num):
    """return True if the number is non-negative"""

    return (num>=0)

################################################################################
#
# Parse functions
#
# @param opt (str) the name of the option being parsed
# @param val (str) the string to parse into a Python object
#
# When we call functions from plugins, we must pass "self" explicitly. However,
# the below functions are bound, and so pass "self" implicitly as well. If we
# called func(self,s) for one of the below functions, the function would
# actually receive func(self,self,s). The @staticmethod decorator fixes this.
#
################################################################################

  # @return (dict of str:class) protocol names and classes to use
  @staticmethod
  def parse_protocols(self,opt,val):
    """parse the protocols and return the subclasses"""

    val = util.split_strip(val,',')
    protocols = {}
    success = False

    for proto in val:

      protocols[proto] = None
      fname = os.path.join('protocols','sibyl_'+proto+os.path.extsep+'py')
      if not os.path.isfile(fname):
        self.log('critical','No matching file in protocols/ for "%s"' % proto)
        continue

      try:
        mod = util.load_module('sibyl_'+proto,'protocols')
        for (name,clas) in inspect.getmembers(mod,inspect.isclass):
          if issubclass(clas,Protocol) and clas!=Protocol:
            protocols[proto] = clas
        if protocols[proto] is None:
          self.log('critical',
              'Protocol "%s" does not contain a lib.protocol.Protocol subclass'
              % proto)

      except Exception as e:
        full = traceback.format_exc(e)
        short = full.split('\n')[-2]
        self.log('critical','Exception importing protocols/%s:'
            % ('sibyl_'+proto))
        self.log('critical','  %s' % short)
        self.log('debug',full)

    if None in protocols.values():
      raise ValueError
    return protocols

  # @return (list) list of plugins to treat as admin
  @staticmethod
  def parse_admin(self,opt,val):
    """parse the list of protocols"""

    return util.split_strip(val,',')

  # @return (list) a list of plugins to disable
  @staticmethod
  def parse_plugins(self,opt,val):
    """parse the list of disabled or enables plugins"""

    # individiual plugins are separated by commas
    val = val.replace('\n','').replace(' ','')
    return val.split(',')

  # @return (dict) map for renaming chat commands
  @staticmethod
  def parse_rename(self,opt,val):
    """parse the rename commands into a dict"""

    d = {}
    for pair in util.split_strip(val,','):
      (old,new) = util.split_strip(pair,':')
      if old in d.keys() or new in d.values():
        raise ValueError
      d[old] = new

    return d

  # @return (dict) a room to join with keys [room, nick, pass]
  @staticmethod
  def parse_rooms(self,opt,val):
    """parse the rooms into a list"""

    val = val.replace('\n','')
    entries = util.split_strip(val,';')
    rooms = {}
    for entry in entries:
      if entry=='':
        continue
      params = util.split_strip(entry,',')
      if not params[0] or ':' not in params[0]:
        self.log('warning','Ignoring room "%s"; invalid syntax' % entry)
        continue
      room = util.split_strip(params[0],':')
      (pname,room) = (room[0],':'.join(room[1:]))

      # check for optional arguments
      room = {'room':room,'nick':None,'pass':None}
      if len(params)>1 and params[1]:
        room['nick'] = params[1]
      if len(params)>2 and params[2]:
        room['pass'] = Password(params[2])

      # add room to dict
      if pname in rooms:
        rooms[pname].append(room)
      else:
        rooms[pname] = [room]
    return rooms

  # @return (int) a log level from the logging module
  @staticmethod
  def parse_log(self,opt,val):
    """parse the specified log level"""

    levels = {'critical' : logging.CRITICAL,
              'error'    : logging.ERROR,
              'warning'  : logging.WARNING,
              'info'     : logging.INFO,
              'debug'    : logging.DEBUG}

    return levels[val]

  # @return (list of tuple) the black/white list
  #   where each tuple contains 3 (str): (color,user,cmd)
  @staticmethod
  def parse_bw(self,opt,val):
    """parse and fully expand the bw_list"""

    val = val.replace('\n','')

    # semi-colons divide separate rules
    entries = util.split_strip(val,';')

    # we don't want to use modifier methods on the actual default object
    bw = copy.copy(self.OPTS[opt][self.DEF])
    for entry in entries:
      if entry=='':
        continue

      # spaces divide fields
      (color,users,cmds) = util.split_strip(entry)

      # skip invalid colors
      if color not in ('b','w'):
        self.log('warning','ignoring bw entry "%s"; invalid color "%s"'
            % (entry,color))
        continue

      # commas allow for multiple items per field
      users = util.split_strip(users,',')
      cmds = util.split_strip(cmds,',')
      for user in users:

        # skip badly formatted users
        if (user!='*' and (
            (not user)
            or (user[0] not in ('p','r','u'))
            or (user[1]!=':')
            or (user[0] in ('r','u') and len(user.split(':'))<3))):
          self.log('warning','ignoring bw user "%s"; invalid syntax' % user)
          continue

        for cmd in cmds:

          # only append the rule if the cmd isn't blank
          if cmd:
            bw.append((color,user,cmd))

    return bw

  # @return (bool)
  @staticmethod
  def parse_bool(self,opt,val):
    """return a bool"""

    if val.strip().lower()=='true':
      return True
    if val.strip().lower()=='false':
      return False
    raise ValueError

  # @return (int)
  @staticmethod
  def parse_int(self,opt,val):
    """return an int"""

    return int(val)

  # @return (float)
  @staticmethod
  def parse_float(self,opt,val):
    """return a float"""

    return float(val)

  # @return (Password)
  @staticmethod
  def parse_pass(self,opt,val):
    """return a Password-object-encapsulated string"""

    return Password(val)

################################################################################
#
# Post functions
#
# @param opts (dict) the parsed values for all options
# @param opt (str) the name of the option being parsed
# @param val (obj) the value of the config option to test
#
# When we call functions from plugins, we must pass "self" explicitly. However,
# the below functions are bound, and so pass "self" implicitly as well. If we
# called func(self,s) for one of the below functions, the function would
# actually receive func(self,self,s). The @staticmethod decorator fixes this.
#
################################################################################

  @staticmethod
  def post_rooms(self,opts,opt,val):
    """make sure all rooms have a valid protocol"""

    for pname in val.keys():
      if pname not in opts['protocols']:
        for room in val[pname]:
          self.log('warning',
              'Ignoring room "%s:%s"; unknown protocol' % (pname,room['room']))
        del val[pname]
    return val

################################################################################
# Logging
################################################################################

  # @param lvl (str) a human-readable log level (e.g. 'debug')
  # @param msg (str) the message to log
  def log(self,lvl,msg):
    """add the message to the queue"""

    if not self.logging:
      return

    if self.real_time:
      self.__log.log(self.parse_log(self,None,lvl),msg)
    else:
      self.log_msgs.append((lvl,msg))

  def process_log(self):
    """should only be called after logging has been initialised in the bot"""

    for (lvl,msg) in self.log_msgs:
      self.__log.log(self.parse_log(self,None,lvl),msg)
    self.clear_log()

  def clear_log(self):
    """clear the log"""

    self.log_msgs = []

################################################################################
# FakeSecHead class
################################################################################

# insert a dummy section header so SafeConfigParser is happy
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
