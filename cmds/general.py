#!/usr/bin/env python

import sys,os,subprocess,json,logging,socket

import requests

from jabberbot import botcmd,botinit
from util import getcell

@botinit
def init(bot):
  """initialise config change tracking variable"""

  bot.conf_diff = {}

@botcmd
def config(bot,mess,args):
  """view and edit config - config (show|set|save|diff) (opt|*) [value]"""

  if not bot.chat_ctrl:
    return "chat_ctrl not enabled"
  
  args = args.split(' ')
  if args[0] not in ('show','set','save','diff'):
    args.insert(0,'show')
  cmd = args[0]
  opt = '*'
  if len(args)>1 and args[1]!='':
    opt = args[1]

  if opt=='*' and cmd=='show':
    return str(bot.conf.opts)
  if opt not in bot.conf.opts and opt!='*':
    return 'Invalid opt'
  if opt in ('username','password'):
    return 'You may not access that option via chat!'

  if cmd=='show':
    return opt+' = '+str(bot.conf.opts[opt])

  if cmd=='diff':
    if len(bot.conf_diff)==0:
      return 'No differences between bot and config file'
    if opt in ('','*'):
      return str(bot.conf_diff.keys())
    if opt not in bot.conf.opts:
      return 'Invalud opt'
    if opt not in bot.conf_diff:
      return 'Opt "'+opt+'" has not changed from config file'
    return 'Opt "'+opt+'" was "'+bot.conf_diff[opt][0]+'" but is now "'+bot.conf.opts[opt]+'"'
  
  if cmd=='set':
    if opt=='*':
      return 'Invalid opt'
    old = bot.conf.opts[opt]
    if bot.conf.set_opt(opt,args[2]):
      bot.conf_diff[opt] = (old,args[2])
      return 'Set opt "'+opt+'" to "'+args[2]+'"'
    else:
      return 'Invalid value for opt "'+opt+'"'

  # logic for 'save' command
  if len(args)>2:
    value = ' '.join(args[2:])
  elif opt in bot.conf_diff:
    value = bot.conf_diff[opt][1]
  elif opt!='*':
    return 'Invalid value'

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
def last(bot,mess,args):
  """display last command (from any chat)"""

  return bot.last_cmd.get(mess.getFrom().getStripped(),'No past commands')

@botcmd
def echo(bot,mess,args):
  """echo some text"""

  return args

@botcmd
def network(bot,mess,args):
  """reply with some network info"""

  s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
  s.connect(('8.8.8.8',80))
  myip = s.getsockname()[0]
  s.close()

  piip = getattr(bot,'xbmc_ip',None)
  exip = requests.get('http://ipecho.net/plain').text.strip()

  return 'My IP - '+myip+' --- RPi IP - '+str(piip)+' --- External IP - '+exip

@botcmd
def die(bot,mess,args):
  """kill sibyl"""

  if not bot.chat_ctrl:
    return 'chat_ctrl disabled'

  bot.quit('Killed via chat_ctrl')

@botcmd
def reboot(bot,mess,args):
  """restart sibyl (currently only works with init.d)"""

  if not bot.chat_ctrl:
    return 'chat_ctrl disabled'

  DEVNULL = open(os.devnull,'wb')
  subprocess.Popen(['service','sibyl','restart'],
      stdout=DEVNULL,stderr=DEVNULL,close_fds=True)
  sys.exit()

@botcmd
def tv(bot,mess,args):
  """pass command to cec-client - tv (on|standby|as)"""

  # sanitize args
  args = ''.join([s for s in args if s.isalpha()])

  PIPE = subprocess.PIPE
  p = subprocess.Popen(['cec-client','-s'],stdin=PIPE,stdout=PIPE,stderr=PIPE)
  (out,err) = p.communicate(args+' 0')

  if err:
    return err
  if 'connection opened' not in out:
    return 'Unknown error'

@botcmd
def ups(bot,mess,args):
  """get latest UPS tracking status - sibyl ups number"""

  # account for connectivity issues
  try:
    url = ('http://wwwapps.ups.com/WebTracking/track?track=yes&trackNums='
        + args + '&loc=en_us')
    page = requests.get(url).text

    # check for invalid tracking number
    if 'The number you entered is not a valid tracking number' in page:
      return 'Invalid tracking number: "'+args+'"'

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

  # search using wikipedia's opensearch json api
  url = ('http://en.wikipedia.org/w/api.php?action=opensearch&search='
      + args + '&format=json')
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

@botcmd
def log(bot,mess,args):
  """set the log level - log (critical|error|warning|info|debug|clear)"""

  if args=='':
    return 'Current level: '+logging.getLevelName(bot.log.getEffectiveLevel()).lower()

  if args=='clear':
    with open(bot.log_file,'w') as f:
      return 'Log cleared'

  levels = ({'critical' : logging.CRITICAL,
             'error'    : logging.ERROR,
             'warning'  : logging.WARNING,
             'info'     : logging.INFO,
             'debug'    : logging.DEBUG})

  level = levels.get(args,'info')
  bot.log.setLevel(level)
  return 'Logging level set to: '+level
