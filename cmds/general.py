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

import sys,os,subprocess,json,logging,socket

import requests

from lib.decorators import *
from lib.util import getcell

@botinit
def init(bot):
  """initialise config change tracking variable"""

  bot.add_var('conf_diff',{})

@botcmd(ctrl=True)
def config(bot,mess,args):
  """view and edit config - config (show|set|save|diff) (opt|*) [value]"""

  # default action is 'show'
  if not args or args[0] not in ('show','set','save','diff'):
    args.insert(0,'show')
  cmd = args[0]
  opt = '*'
  if len(args)>1 and args[1]!='':
    opt = args[1]

  if opt=='*' and cmd=='show':
    return str(bot.opt())
  if opt not in bot.opt() and opt!='*':
    return 'Invalid opt'
  if opt=='password':
    return 'You may not access that option via chat!'

  # return the value of the specified opt
  if cmd=='show':
    return opt+' = '+str(bot.opt(opt))

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
    return 'Opt "'+opt+'" was "'+bot.conf_diff[opt][0]+'" but is now "'+bot.opt[opt]+'"'

  # some options don't make sense to edit in chat
  if opt in ('chat_proto','username','disabled','cmd_dir'):
    return 'You may not edit that option via chat'

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

  # save all changed opts
  if opt=='*':
    for opt in bot.conf_diff:
      bot.conf.save_opt(opt,bot.conf_diff[opt][1])
    opts = bot.conf_diff.keys()
    bot.conf_diff = {}
    return 'Saved opts: '+str(opts)
  
  if bot.conf.save_opt(opt,value):
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

  xbmc = None
  if 'xbmc_ip' in bot.opt():
    xbmc = bot.opt('xbmc_ip')
  exip = requests.get('http://ipecho.net/plain').text.strip()

  return 'My IP - '+myip+' --- XBMC IP - '+str(xbmc)+' --- External IP - '+exip

@botcmd(ctrl=True)
def die(bot,mess,args):
  """kill sibyl"""

  bot.quit('Killed via chat_ctrl')

@botcmd(ctrl=True)
def reboot(bot,mess,args):
  """restart sibyl (currently only works with init.d)"""

  DEVNULL = open(os.devnull,'wb')
  subprocess.Popen(['sudo','-n','/etc/init.d/sibyl','restart'],
      stdout=DEVNULL,stderr=DEVNULL,close_fds=True)
  bot.quit('reboot by chat_ctrl')

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
  """set the log level - log (critical|error|warning|info|debug|clear)"""

  # default action is to print current level
  if not args:
    return ('Current level: '+
        logging.getLevelName(bot.log.getEffectiveLevel()).lower())

  # clear the log
  if args[0]=='clear':
    with open(bot.opt('log_file'),'w') as f:
      return 'Log cleared'

  # set the log level for this instance only
  levels = ({'critical' : logging.CRITICAL,
             'error'    : logging.ERROR,
             'warning'  : logging.WARNING,
             'info'     : logging.INFO,
             'debug'    : logging.DEBUG})

  level = levels.get(args[0],logging.INFO)
  bot.log.setLevel(level)
  return 'Logging level set to: '+logging.getLevelName(level)
