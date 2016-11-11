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

import sys,os,subprocess,json,logging,socket,re,codecs

import requests

from sibyl.lib.decorators import *
from sibyl.lib.util import getcell,is_int
from sibyl.lib.protocol import Message

@botconf
def conf(bot):
  """add config option"""

  return [
    {'name':'config_rooms','default':True,'parse':bot.conf.parse_bool},
    {'name':'log_time','default':True,'parse':bot.conf.parse_bool},
    {'name':'log_lines','default':10,'parse':bot.conf.parse_int},
    {'name':'alias_file','default':'data/aliases.txt','valid':bot.conf.valid_wfile}
  ]

@botinit
def init(bot):
  """initialise config change tracking variable"""

  bot.add_var('conf_diff',{})
  bot.add_var('aliases',{})
  try:
    bot.aliases = alias_read(bot)
  except Exception as e:
    bot.log.error('Failed to parse alias_file')
    bot.log.debug(e.message)

@botcmd
def alias(bot,mess,args):
  """add aliases for cmds (and args) - alias (info|list|add|remove|show) [name] [cmd]"""

  if not args:
    args = ['info']

  if args[0]=='list':
    aliases = bot.aliases.keys()
    if not aliases:
      return 'There are no aliases'
    return ', '.join(sorted(aliases))

  elif args[0]=='add':
    if len(args)<2:
      return 'You must specify a name and content'
    if len(args)<3:
      return 'You must specify some text'
    (name,text) = (args[1],' '.join(args[2:]))

    if name in bot.aliases:
      return 'An alias already exists by that name'
    if name in [h._sibylbot_dec_chat_name for h in bot.hooks['chat'].values()]:
      return 'The %s plugin has a chat command by that name' % bot.ns_cmd[name]
    if name==args[2]:
      return 'An alias cannot reference itself'

    bot.aliases[name] = text
    alias_write(bot)
    return 'Added alias "%s"' % name

  elif args[0]=='remove':
    if len(args)<2:
      return 'You must specify an alias to remove'
    if args[1]=='*':
      bot.aliases = {}
      alias_write(bot)
      return 'Removed all aliases'
    if args[1] not in bot.aliases:
      return 'Invalid alias'
    del bot.aliases[args[1]]
    return 'Removed alias "%s"' % args[1]

  elif args[0]=='show':
    if len(args)<2:
      return 'You must specify an alias'
    if args[1] not in bot.aliases:
      return 'Invalid alias'
    return bot.aliases[args[1]]

  return 'There are %s aliases' % len(bot.aliases)

@botmsg
def alias_cb(bot,mess,cmd):
  """execute aliases"""

  if not cmd:
    return

  name = cmd[0]
  if name in bot.aliases:

    new = bot.aliases[name]
    bot.log.debug('cmd "%s" is an alias for "%s"' % (name,new))

    orig = mess.get_text()
    for n in new.split(';'):
      n = n.strip()
      if not n:
        continue
      text = ' '.join([n]+orig.split(' ')[1:])
      room = mess.get_from().get_room()
      if room:
        text = bot.get_protocol(mess).get_nick(room)+' '+text
      mess.set_text(text)
      bot._cb_message(mess)

def alias_read(bot):
  """read aliases from file into dict"""

  fname = bot.opt('general.alias_file')

  if os.path.isfile(fname):
    with codecs.open(fname,'r',encoding='utf8') as f:
      lines = f.readlines()
  else:
    lines = []
    alias_write(bot)

  aliases = {}
  for (i,line) in enumerate(lines):
    try:
      if line.strip():
        (name,text) = line.split('\t')
        aliases[name.lower().strip()] = text.strip()
    except Exception as e:
      raise IOError('Error parsing alias_file at line %s' % i)

  removed = False
  for name in aliases.keys():
    if name in [h._sibylbot_dec_chat_name for h in bot.hooks['chat'].values()]:
      removed = True
      del aliases[name]
      bot.log.warning('Ignoring alias "%s"; conflicts with cmd from plugin %s'
          % (name,bot.ns_cmd[name]))

  if removed:
    bot.errors.append('Some aliases ignored due to name conflicts')

  return aliases

def alias_write(bot):
  """write aliases from bot to file"""

  a = [(k,v) for (k,v) in sorted(bot.aliases.items(),key=lambda i:i[0])]
  lines = [(name+'\t'+text+'\n') for (name,text) in a]

  with codecs.open(bot.opt('general.alias_file'),'w',encoding='utf8') as f:
    f.writelines(lines)

@botcmd(ctrl=True)
def config(bot,mess,args):
  """view and edit config - config (show|set|save|diff|reset) (opt|*) [value]"""

  if (not bot.opt('general.config_rooms')) and mess.get_type()==Message.GROUP:
    return 'The config command is disabled in rooms'

  # default action is 'show'
  if not args or args[0] not in ('show','set','save','diff','reset'):
    args.insert(0,'show')
  cmd = args[0]
  opt = '*'
  if len(args)>1 and args[1]!='':
    opt = args[1]

  if opt=='*' and cmd=='show':
    opts = bot.opt()
    for opt in opts:
      if opt.endswith('password'):
        opts[opt] = 'REDACTED'
    for proto in opts['rooms']:
      for room in opts['rooms'][proto]:
        if room['pass']:
          room['pass'] = 'REDACTED'
    return str(opts)
  if opt not in bot.opt() and opt!='*':
    return 'Invalid opt'
  if opt.endswith('password'):
    return 'You may not access passwords via chat!'

  # return the value of the specified opt
  if cmd=='show':
    val = bot.opt(opt)
    if opt=='rooms':
      for proto in val:
        for room in val[proto]:
          if room['pass']:
            room['pass'] = 'REDACTED'
    return opt+' = '+str(val)

  # return opt values that have been edited but not saved
  if cmd=='diff':
    if len(bot.conf_diff)==0:
      return 'No differences between bot and config file'
    if opt in ('','*'):
      return str(bot.conf_diff.keys())
    if opt not in bot.opt():
      return 'Invalud opt'
    if opt not in bot.conf_diff:
      return 'Opt "'+opt+'" has not changed from config file'
    return ('Opt "%s" was "%s" but is now "%s"'
        % (opt,bot.conf_diff[opt][0],bot.opt[opt]))

  # some options don't make sense to edit in chat
  if opt in ('protocols','disabled','enabled','cmd_dir','rooms'):
    return 'You may not edit that option via chat'

  # revert to original config
  if cmd=='reset':
    if len(bot.conf_diff)==0:
      return 'No config options to reset'
    if opt in ('','*'):
      opts = bot.conf_diff.keys()
      for opt in opts:
        bot.conf.opts[opt] = bot.conf_diff[opt][0]
      bot.conf_diff = {}
      return 'Reset opts: %s' % opts
    if opt not in bot.opt():
      return 'Invalid opt'
    if opt not in bot.conf_diff:
      return 'Opt "%s" has not been changed' % opt
    bot.conf.opts[opt] = bot.conf_diff[opt][0]
    del bot.conf_diff[opt]
    return 'Reset "%s" to "%s"' % (opt,bot.opt(opt))

  # set opt values in this bot instance only
  if cmd=='set':
    if opt=='*':
      return 'Invalid opt'
    old = bot.opt(opt)
    if bot.conf.set_opt(opt,args[2]):
      bot.conf_diff[opt] = (old,args[2])
      return 'Set opt "'+opt+'" to "'+args[2]+'"'
    else:
      return 'Invalid value for opt "'+opt+'"'

  # logic for 'save' command that also modified the config file
  if len(args)>2:
    value = ' '.join(args[2:])
  elif opt in bot.conf_diff:
    value = bot.conf_diff[opt][1]
  elif opt!='*':
    return 'Invalid value'

  name = mess.get_from().get_real().get_base()

  # save all changed opts
  if opt=='*':
    for opt in bot.conf_diff:
      bot.conf.save_opt(opt,bot.conf_diff[opt][1],name)
    opts = bot.conf_diff.keys()
    bot.conf_diff = {}
    return 'Saved opts: '+str(opts)

  if bot.conf.save_opt(opt,value,name):
    if opt in bot.conf_diff:
      del bot.conf_diff[opt]
    return 'Saved opt "'+opt+'" to be "'+value+'"'
  return 'Invalid value for opt "'+opt+'"'

@botcmd
def echo(bot,mess,args):
  """echo some text"""

  return ' '.join(args)

@botcmd
def network(bot,mess,args):
  """reply with some network info"""

  s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
  s.connect(('8.8.8.8',80))
  myip = s.getsockname()[0]
  s.close()

  xbmc = bot.opt('xbmc.ip')
  exip = requests.get('http://ipecho.net/plain').text.strip()

  return 'My IP - '+myip+' --- XBMC IP - '+xbmc+' --- External IP - '+exip

@botcmd(ctrl=True)
def die(bot,mess,args):
  """kill sibyl"""

  bot.quit('Killed via chat_ctrl')

@botcmd(ctrl=True)
def reboot(bot,mess,args):
  """restart sibyl (currently only works with init.d)"""

  bot.reboot('Reboot via chat_ctrl')

@botcmd
def tv(bot,mess,args):
  """pass command to cec-client - tv (on|standby|as)"""

  if not args:
    args = ['pow']

  # sanitize args
  args = ''.join([s for s in args[0] if s.isalpha()])

  PIPE = subprocess.PIPE
  p = subprocess.Popen(['cec-client','-s'],stdin=PIPE,stdout=PIPE,stderr=PIPE)
  (out,err) = p.communicate(args+' 0')

  # do some basic error checking
  if err:
    return err
  if 'connection opened' not in out:
    return 'Unknown error'

  # if the user requested power state, return that
  if args=='pow':
    for line in out.split('\n'):
      if 'power status:' in line:
        return line

@botcmd
def ups(bot,mess,args):
  """get latest UPS tracking status - sibyl ups number"""

  if not args:
    return 'You must provide a tracking number'

  # account for connectivity issues
  try:
    url = ('http://wwwapps.ups.com/WebTracking/track?track=yes&trackNums='
        + args[0] + '&loc=en_us')
    page = requests.get(url).text

    # check for invalid tracking number
    if 'The number you entered is not a valid tracking number' in page:
      return 'Invalid tracking number: "'+args[0]+'"'

    # find and return some relevant info
    start = page.find('Activity')
    (location,start) = getcell(start+1,page)
    (newdate,start) = getcell(start+1,page)
    (newtime,start) = getcell(start+1,page)
    (activity,start) = getcell(start+1,page)
    timestamp = newdate + ' ' + newtime
    return timestamp+' - '+location+' - '+activity

  except:
    return 'Unknown error accessing UPS website'

@botcmd
def wiki(bot,mess,args):
  """return a link and brief from wikipedia - wiki title"""

  if not args:
    return 'You must provide a search term'

  # search using wikipedia's opensearch json api
  url = ('http://en.wikipedia.org/w/api.php?action=opensearch&search='
      + ' '.join(args) + '&format=json')
  response = requests.get(url)
  result = json.loads(response.text)
  title = result[1][0]
  text = result[2]

  # don't send the unicode specifier in the reply message
  try:
    text.remove(u'')
    text = '\n'.join(text)
  except ValueError:
    pass

  # send a link and brief back to the user
  url = result[3][0]
  return unicode(title)+' - '+unicode(url)+'\n'+unicode(text)

@botcmd(ctrl=True)
def log(bot,mess,args):
  """set the log level - log (info|level|clear|tail|trace)"""

  # default print some info
  if not args:
    args = ['info']

  # control log level
  if args[0]=='level':

    if len(args)<2:
      return ('Current level: '+
          logging.getLevelName(bot.log.getEffectiveLevel()).lower())

    # set the log level for this instance only
    levels = ({'critical' : logging.CRITICAL,
               'error'    : logging.ERROR,
               'warning'  : logging.WARNING,
               'info'     : logging.INFO,
               'debug'    : logging.DEBUG})

    level = levels.get(args[1],logging.INFO)
    logging.getLogger().setLevel(level)
    return 'Logging level set to: '+logging.getLevelName(level)

  # clear the log
  elif args[0]=='clear':

    with open(bot.opt('log_file'),'w') as f:
      return 'Log cleared'

  # return the last n lines from the log file
  elif args[0]=='tail':

    n = bot.opt('general.log_lines')
    r = None

    # check if the user specified a number of lines
    if len(args)>1:
      if is_int(args[1]):
        n = int(args[1])
        del args[1]

    # check if the user specified a regex
    if len(args)>1:
      r = ' '.join(args[1:])

    # return n lines matching regex
    with open(bot.opt('log_file'),'r') as f:
      lines = f.readlines()
    if r:
      lines = [l for l in lines if re.search(r,l)]
    lines = lines[-n:]
    if not bot.opt('general.log_time'):
      lines = [(l[l.find('|')+2:] if l.find('|') else l) for l in lines]
    return ''.join(lines[:n])

  # return the last traceback
  elif args[0]=='trace':

    with open(bot.opt('log_file'),'r') as f:
      lines = f.readlines()

    start = -1
    for (i,l) in enumerate(lines):
      if 'Traceback (most recent call last):' in l:
        start = i
    if start==-1:
      return 'No traceback in logs'
    lines = lines[start:]
    end = -1
    for (i,l) in enumerate(lines):
      if l.strip()=='':
        end = i
        break
    return ''.join(lines[:end])

  # print log file stats
  fname = os.path.abspath(bot.opt('log_file'))
  fsize = os.path.getsize(fname)/1000.0
  with open(fname,'r') as f:
    for (i,l) in enumerate(f):
      pass
  lines = i+1
  return 'Log file %s is %.1fKB with %s lines' % (fname,fsize,lines)
