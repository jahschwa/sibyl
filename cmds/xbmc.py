#!/usr/bin/env python

import random,requests

from sibyl.jabberbot import botcmd,botfunc,botinit
from sibyl.sibylbot import botconf
import sibyl.util as util

@botconf
def conf(bot):
  """add config options"""

  return [{'name' : 'rpi_ip',
            'def' : '127.0.0.1',
            'valid' : bot.conf.valid_ip},
          {'name' : 'xbmc_user'},
          {'name' : 'xbmc_pass'}]

@botcmd
def remote(bot,mess,args):
  """execute remote buttons in order - remote (lrudeb)[...]"""

  cmds = {'u':'Input.Up',
          'd':'Input.Down',
          'l':'Input.Left',
          'r':'Input.Right',
          'e':'Input.Select',
          'b':'Input.Back'}

  raw = ''.join(args)
  cmd = [s for s in raw if s in cmds]
  for s in cmd:
    bot.xbmc(cmds[s])

@botcmd
def volume(bot,mess,args):
  """set the player volume percentage - volume %"""

  # if no arguments are passed, return the current volume
  if len(args.strip())==0:
    result = bot.xbmc('Application.GetProperties',{'properties':['volume']})
    vol = result['result']['volume']
    return 'Current volume: '+str(vol)+'%'

  # otherwise try to set the volume
  args = args.replace('%','')
  try:
    val = int(args.strip())
  except ValueError as e:
    val = -1

  if val<0 or val>100:
    return 'Argument to "volume" must be an integer from 0-100'

  bot.xbmc('Application.SetVolume',{'volume':val})

@botcmd
def subtitles(bot,mess,args):
  """change the subtitles - subtitles (info|on|off|next|prev|set) [index]"""

  args = args.split(' ')
  pid = bot.xbmc_active_player()
  if pid!=1:
    return 'No video playing'

  if args[0]=='prev':
    args[0] = 'previous'

  if args[0]=='on' or args[0]=='off' or args[0]=='next' or args[0]=='previous':
    bot.xbmc('Player.SetSubtitle',{'playerid':pid,'subtitle':args[0]})
    if args[0]=='off':
      return
    subs = bot.xbmc('Player.GetProperties',{'playerid':1,
        'properties':['currentsubtitle']})
    subs = subs['result']['currentsubtitle']
    return 'Subtitle: '+str(subs['index'])+'-'+subs['language']+'-'+subs['name']

  subs = bot.xbmc('Player.GetProperties',{'playerid':1,
      'properties':['subtitles','currentsubtitle']})
  cur = subs['result']['currentsubtitle']
  subs = subs['result']['subtitles']

  if args[0]=='set':
    try:
      index = int(args[1])
    except ValueError as e:
      return 'Index must be an integer'

    if (index<0) or (index>len(subs)-1):
      return 'Index must be in [0,'+str(len(subs)-1)+']'
    cur = cur['index']
    if index==cur:
      return 'That is already the active subtitle'
    elif index<cur:
      diff = cur-index
      func = 'prev'
    else:
      diff = index-cur
      func = 'next'

    for i in range(0,diff):
      bot.subtitles(None,func)
    return

  sub = []
  for i in range(0,len(subs)):
    for s in subs:
      if i==s['index']:
        sub.append(subs[i])
        continue

  s = 'Subtitles: '
  for x in sub:
    if x['index']==cur['index']:
      s += '('
    s += str(x['index'])+'-'+x['language']+'-'+x['name']
    if x['index']==cur['index']:
      s += ')'
    s += ', '
  return s[:-2]

@botcmd
def info(bot,mess,args):
  """display info about currently playing file"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return 'Nothing playing'

  # get file name
  result = bot.xbmc('Player.GetItem',{'playerid':pid})
  name = result['result']['item']['label']

  # get speed, current time, and total time
  result = bot.xbmc('Player.GetProperties',{'playerid':pid,'properties':['speed','time','totaltime']})
  current = result['result']['time']
  total = result['result']['totaltime']

  # translate speed: 0 = 'paused', 1 = 'playing'
  speed = result['result']['speed']
  status = 'playing'
  if speed==0:
    status = 'paused'

  playlists = ['Audio','Video','Picture']
  return playlists[pid]+' '+status+' at '+util.time2str(current)+'/'+util.time2str(total)+' - "'+name+'"'

@botcmd
def play(bot,mess,args):
  """if xbmc is paused, resume playing"""

  bot.playpause(0)

@botcmd
def pause(bot,mess,args):
  """if xbmc is playing, pause"""

  bot.playpause(1)

@botcmd
def stop(bot,mess,args):
  """if xbmc is playing, stop"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  bot.xbmc('Player.Stop',{"playerid":pid})

@botcmd
def prev(bot,mess,args):
  """go to previous playlist item"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  # the first call goes to 0:00, the second actually goes back in playlist
  bot.xbmc('Player.GoTo',{'playerid':pid,'to':'previous'})
  bot.xbmc('Player.GoTo',{'playerid':pid,'to':'previous'})

@botcmd
def next(bot,mess,args):
  """go to next playlist item"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  bot.xbmc('Player.GoTo',{'playerid':pid,'to':'next'})

@botcmd
def jump(bot,mess,args):
  """jump to an item# in the playlist - jump #"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  # try to parse the arg to an int
  try:
    num = int(args.split(' ')[-1])-1
    bot.xbmc('Player.GoTo',{'playerid':pid,'to':num})
    return None
  except ValueError:
    return 'Playlist position must be an integer greater than 0'

@botcmd
@botfunc
def seek(bot,mess,args):
  """go to a specific time - seek [hh:]mm:ss"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  # try to parse the arg as a time
  try:
    t = args.split(' ')[-1]
    c1 = t.find(':')
    c2 = t.rfind(':')
    s = int(t[c2+1:])
    h = 0
    if c1==c2:
      m = int(t[:c1])
    else:
      m = int(t[c1+1:c2])
      h = int(t[:c1])
    bot.xbmc('Player.Seek',{'playerid':pid,'value':{'hours':h,'minutes':m,'seconds':s}})
  except ValueError:
    return 'Times must be in the format m:ss or h:mm:ss'

@botcmd
def restart(bot,mess,args):
  """start playing again from 0:00"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  bot.xbmc('Player.Seek',{'playerid':pid,'value':{'seconds':0}})

@botcmd
def hop(bot,mess,args):
  """move forward or back - hop [small|big] [back|forward]"""

  # abort if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  # check for 'small' (default) and 'big'
  s = ''
  if 'big' in args:
    s += 'big'
  else:
    s += 'small'

  # check for 'back' (default) and 'forward'
  if 'forward' in args:
    s += 'forward'
  else:
    s += 'backward'

  bot.xbmc('Player.Seek',{'playerid':pid,'value':s})

@botcmd
def stream(bot,mess,args):
  """stream from [YouTube, Twitch (Live)] - stream url"""

  agent = {'User-agent':'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:46.0) Gecko/20100101 Firefox/46.0'}
  msg = args

  # remove http:// https:// www. from start
  msg = msg.replace('http://','').replace('https://','').replace('www.','')

  # account for mobile links from youtu.be and custom start times
  if msg.lower().startswith('youtu.be'):
    tim = None
    if '?t=' in msg:
      tim = msg[msg.find('?t=')+3:]
      msg = msg[:msg.find('?t=')]
    msg = 'youtube.com/watch?v='+msg[msg.rfind('/')+1:]
    if tim:
      msg += ('&t='+tim)

  # account for "&start=" custom start times
  msg = msg.replace('&start=','&t=')

  # parse youtube links
  if msg.lower().startswith('youtube'):

    #check for custom start time
    tim = None
    if '&t=' in msg:
      start = msg.find('&t=')+3
      end = msg.find('&',start+1)
      if end==-1:
        end = len(msg)
      tim = msg[start:end]

      # get raw seconds from start time
      sec = 0
      if 'h' in tim:
        sec += 3600*int(tim[:tim.find('h')])
        tim = tim[tim.find('h')+1:]
      if 'm' in tim:
        sec += 60*int(tim[:tim.find('m')])
        tim = tim[tim.find('m')+1:]
      if 's' in tim:
        sec += int(tim[:tim.find('s')])
        tim = ''
      if len(tim)>0:
        sec = int(tim)

      # parse seconds to 'h:mm:ss'
      tim = {'hours':0,'minutes':0,'seconds':0}
      if int(sec/3600)>0:
        tim['hours'] = int(sec/3600)
        sec -= 3600*tim['hours']
      if int(sec/60)>0:
        tim['minutes'] = int(sec/60)
        sec -= 60*tim['minutes']
      tim['seconds'] = sec
      tim = util.time2str(tim)

    # remove feature, playlist, etc info from end and get vid
    if '&' in msg:
      msg = msg[:msg.find('&')]
    vid = msg[msg.find('watch?v=')+8:]

    # retrieve video info from webpage
    html = requests.get('http://youtube.com/watch?v='+vid,headers=agent).text
    title = html[html.find('<title>')+7:html.find(' - YouTube</title>')]
    title = util.cleanhtml(title)
    channel = html.find('class="yt-user-info"')
    start = html.find('>',channel+1)
    start = html.find('>',start+1)+1
    stop = html.find('<',start+1)
    channel = html[start:stop]

    # send xbmc request and seek if given custom start time
    bot.xbmc('Player.Open',{'item':{'file':'plugin://plugin.video.youtube/play/?video_id='+vid}})
    if tim:
      bot.seek(None,tim)

    # respond to the user with video info
    s = 'Streaming "'+title+'" by "'+channel+'" from YouTube'
    if tim:
      s += (' at '+tim)
    return s

  elif 'twitch' in msg.lower():

    vid = msg[msg.find('twitch.tv/')+10:]
    html = requests.get('http://twitch.tv/'+vid,headers=agent).text

    stream = html.find("property='og:title'")
    stop = html.rfind("'",0,stream)
    start = html.rfind("'",0,stop)+1
    stream = html[start:stop]

    title = html.find("property='og:description'")
    stop = html.rfind("'",0,title)
    start = html.rfind("'",0,stop)+1
    title = html[start:stop]

    response = bot.xbmc('Player.Open',{'item':{'file':'plugin://plugin.video.twitch/playLive/'+vid}})
    return 'Streaming "'+title+'" by "'+stream+'" from Twitch Live'

  else:
    return 'Unsupported URL'

@botcmd
@botfunc
def videos(bot,mess,args):
  """search and open a folder as a playlist - videos [include -exclude] [track#]"""

  return bot.files(args,bot.lib_video_dir,1)

@botcmd
def video(bot,mess,args):
  """search and play a single video - video [include -exclude]"""

  return bot.file(args,bot.lib_video_file)

@botcmd
@botfunc
def audios(bot,mess,args):
  """search and open a folder as a playlist - audios [include -exclude] [track#]"""

  return bot.files(args,bot.lib_audio_dir,0)

@botcmd
def audio(bot,mess,args):
  """search and play a single audio file - audio [include -exclude]"""

  return bot.file(args,bot.lib_audio_file)

@botcmd
@botfunc
def fullscreen(bot,mess,args):
  """toggle fullscreen"""

  bot.xbmc('GUI.SetFullscreen',{'fullscreen':'toggle'})

@botcmd
def random(bot,mess,args):
  """play random song - random [include -exclude]"""

  # check if a search term was passed
  name = args.split(' ')
  if args=='':
    _matches = bot.lib_audio_file
  else:
    _matches = util.matches(bot.lib_audio_file,name)

  if len(_matches)==0:
    return 'Found 0 matches'

  # play a random audio file from the matches
  rand = random.randint(0,len(_matches)-1)

  result = bot.xbmc('Player.Open',{'item':{'file':_matches[rand]}})
  if 'error' in result.keys():
    s = 'Unable to open: '+_matches[rand]
    bot.log.error(s)
    return s

  bot.xbmc('GUI.SetFullscreen',{'fullscreen':True})

  return 'Playing "'+_matches[rand]+'"'

@botfunc
def xbmc(bot,method,params=None):
  """wrapper method to always provide IP to static method"""

  return util.xbmc(bot.rpi_ip,method,params,bot.xbmc_user,bot.xbmc_pass)

@botfunc
def xbmc_active_player(bot):
  """wrapper method to always provide IP to static method"""

  return util.xbmc_active_player(bot.rpi_ip,bot.xbmc_user,bot.xbmc_pass)

@botfunc
def playpause(bot,target):
  """helper function for play() and pause()"""

  # return None if nothing is playing
  pid = bot.xbmc_active_player()
  if pid is None:
    return None

  # check player status before sending PlayPause command
  speed = bot.xbmc('Player.GetProperties',{'playerid':pid,'properties':["speed"]})
  speed = speed['result']['speed']
  if speed==target:
    bot.xbmc('Player.PlayPause',{"playerid":pid})

@botfunc
def files(bot,args,dirs,pid):
  """helper function for videos() and audios()"""

  # check for item# as last arg
  args = args.split(' ')
  num = None
  try:
    num = int(args[-1])-1
  except ValueError:
    pass

  # default is 0 if not specified
  if num is None:
    num = 0
    name = args
  else:
    name = args[:-1]

  # find matches and respond if len(matches)!=1
  _matches = util.matches(dirs,name)

  if len(_matches)==0:
    return 'Found 0 matches'

  # default to top dir if every match is a sub dir
  _matches = util.reducetree(_matches)

  if len(_matches)>1:
    if bot.max_matches<1 or len(_matches)<=bot.max_matches:
      return 'Found '+str(len(_matches))+' matches: '+util.list2str(_matches)
    else:
      return 'Found '+str(len(_matches))+' matches'

  # if there was 1 match, add the whole directory to a playlist
  # also check for an error opening the directory
  bot.xbmc('Playlist.Clear',{'playlistid':pid})

  result = bot.xbmc('Playlist.Add',{'playlistid':pid,'item':{'directory':_matches[0]}})
  if 'error' in result.keys():
    s = 'Unable to open: '+_matches[0]
    bot.log.error(s)
    return s

  bot.xbmc('Player.Open',{'item':{'playlistid':pid,'position':num}})
  bot.xbmc('GUI.SetFullscreen',{'fullscreen':True})

  # set last_played for bookmarking
  bot.last_played = (pid,_matches[0])

  return 'Playlist from "'+_matches[0]+'" starting with #'+str(num+1)

@botfunc
def file(bot,args,dirs):
  """helper function for video() and audio()"""

  name = args.split(' ')

  # find matches and respond if len(matches)!=1
  _matches = util.matches(dirs,name)

  if len(_matches)==0:
    return 'Found 0 matches'

  if len(_matches)>1:
    if bot.max_matches<1 or len(_matches)<=bot.max_matches:
      return 'Found '+str(len(_matches))+' matches: '+util.list2str(_matches)
    else:
      return 'Found '+str(len(_matches))+' matches'

  # if there was 1 match, play the file, and check for not found error
  result = bot.xbmc('Player.Open',{'item':{'file':_matches[0]}})
  if 'error' in result.keys():
    s = 'Unable to open: '+_matches[0]
    bot.log.error(s)
    return s

  bot.xbmc('GUI.SetFullscreen',{'fullscreen':True})

  # clear last_played
  bot.last_played = None

  return 'Playing "'+_matches[0]+'"'
