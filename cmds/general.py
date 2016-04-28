#!/usr/bin/env python

import sys,os,subprocess,json,logging,socket

import requests

from sibyl.jabberbot import botcmd,botfunc
from sibyl.util import getcell

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

  piip = getattr(bot,'rpi_ip',None)
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

  cmd = ['echo',args+' 0']
  cec = ['cec-client','-s']

  # execute echo command and pipe output to PIPE
  p = subprocess.Popen(cmd,stdout=subprocess.PIPE)

  # execute cec-client using PIPE as input and sending output to /dev/null
  DEVNULL = open(os.devnull,'wb')
  subprocess.call(cec,stdin=p.stdout,stdout=DEVNULL,close_fds=True)

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
