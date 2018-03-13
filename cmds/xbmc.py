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

import random,requests,json,os

from sibyl.lib.decorators import *
import sibyl.lib.util as util

import logging
log = logging.getLogger(__name__)

__wants__ = ['library']

@botconf
def conf(bot):
  """add config options"""

  return [{'name' : 'ip',
            'default' : '127.0.0.1:8080',
            'required' : True,
            'valid' : bot.conf.valid_ip},

          {'name' : 'username'},

          {'name' : 'password'},

          {'name' : 'timeout',
            'default' : 15,
            'parse' : bot.conf.parse_int,
            'valid' : bot.conf.valid_nump}
  ]

@botinit
def init(bot):
  """create empty vars"""

  bot.add_var('last_played',persist=True)

@botcmd
def remote(bot,mess,args):
  """execute remote buttons in order - remote (lrudebc)[...]"""

  cmds = {'u':'Input.Up',
          'd':'Input.Down',
          'l':'Input.Left',
          'r':'Input.Right',
          'e':'Input.Select',
          'b':'Input.Back',
          'c':'Input.ContextMenu'}

  raw = ''.join(args)
  cmd = [s for s in raw if s in cmds]
  for s in cmd:
    bot.xbmc(cmds[s])

@botcmd
def volume(bot,mess,args):
  """set the player volume percentage - volume %"""

  # if no arguments are passed, return the current volume
  if not args:
    result = bot.xbmc('Application.GetProperties',{'properties':['volume']})
    vol = result['result']['volume']
    return 'Current volume: '+str(vol)+'%'

  # otherwise try to set the volume
  args = args[0].replace('%','')
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

  # default action is 'info'
  if not args:
    args = ['info']

  # return if nothing is playing
  active = bot.xbmc_active_player()
  if not active or active[1]!='video':
    return 'No video playing'
  (pid,typ) = active

  if args[0]=='prev':
    args[0] = 'previous'

  # change subtitles
  if args[0]=='on' or args[0]=='off' or args[0]=='next' or args[0]=='previous':
    bot.xbmc('Player.SetSubtitle',{'playerid':pid,'subtitle':args[0]})
    if args[0]=='off':
      return
    subs = bot.xbmc('Player.GetProperties',{'playerid':pid,
        'properties':['currentsubtitle']})
    subs = subs['result']['currentsubtitle']
    return 'Subtitle: '+str(subs['index'])+'-'+subs['language']+'-'+subs['name']

  # get subtitles
  subs = bot.xbmc('Player.GetProperties',{'playerid':pid,
      'properties':['subtitles','currentsubtitle']})
  cur = subs['result']['currentsubtitle']
  subs = subs['result']['subtitles']

  # allow the user to specify an index from the list
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
      bot.run_cmd('subtitles',[func])
    return

  # else return a list of all the subtitles
  sub = []
  for i in range(0,len(subs)):
    for s in subs:
      if i==s['index']:
        sub.append(subs[i])

  if not len(sub):
    return 'No subtitles'

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
  active = bot.xbmc_active_player()
  if not active:
    return 'Nothing playing'
  (pid,typ) = active

  # get file name
  result = bot.xbmc('Player.GetItem',{'playerid':pid})
  name = result['result']['item']['label']

  # get speed, current time, and total time
  result = bot.xbmc('Player.GetProperties',
      {'playerid':pid,'properties':['speed','time','totaltime']})
  current = util.time2str(result['result']['time'])
  total = util.time2str(result['result']['totaltime'])

  # translate speed: 0 = 'paused', 1 = 'playing'
  speed = result['result']['speed']
  status = 'playing'
  if speed==0:
    status = 'paused'

  return '%s %s at %s/%s - "%s"' % (typ.title(),status,current,total,name)

@botcmd
def play(bot,mess,args):
  """unpause, or play a file - play [/path | http://url | smb://server/share/path]"""

  # if no args are passed, start playing again
  if not args:
    playpause(bot,0)
    return

  if bot.has_plugin('library'):
    path = bot.library_translate(args[0])

  # if args are passed, play the specified file
  # [TODO] make work with samba shares requiring passwords
  if (path.startswith('smb://') or os.path.isfile(path)
      or path.startswith('http')):
    result = bot.xbmc('Player.Open',{'item':{'file':path}})
    if 'error' in result:
      s = 'Unable to open: %s (%s)' % (path,result['error']['message'])
      log.info(s)
      return s
    return bot.run_cmd('info')
  return 'Invalid file'

@botcmd
def pause(bot,mess,args):
  """if xbmc is playing, pause"""

  playpause(bot,1)

@botcmd
def stop(bot,mess,args):
  """if xbmc is playing, stop"""

  # abort if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  bot.xbmc('Player.Stop',{"playerid":pid})

@botcmd
def prev(bot,mess,args):
  """go to previous playlist item"""

  # abort if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  # the "previous" option for GoTo seems to not work consistently in XBMC
  params = {'playlistid':pid,'properties':['size']}
  siz = bot.xbmc('Playlist.GetProperties',params)['result']['size']

  params = {'playerid':pid,'properties':['position']}
  pos = bot.xbmc('Player.GetProperties',params)['result']['position']

  pos = min(siz-1,max(0,pos-1))
  bot.run_cmd('jump',[str(pos+1)])

@botcmd
def next(bot,mess,args):
  """go to next playlist item"""

  # abort if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  bot.xbmc('Player.GoTo',{'playerid':pid,'to':'next'})

@botcmd
def jump(bot,mess,args):
  """jump to an item# in the playlist - jump #"""

  # abort if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  if not args:
    return 'You must specify a playlist position'

  # try to parse the arg to an int
  try:
    num = int(args[0])-1
    bot.xbmc('Player.GoTo',{'playerid':pid,'to':num})
    return None
  except ValueError:
    return 'Playlist position must be an integer greater than 0'

@botcmd
def seek(bot,mess,args):
  """go to a specific time - seek [hh:]mm:ss"""

  # abort if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  if not args:
    return 'You must specify a time'

  # try to parse the arg as a time
  try:
    t = util.str2time(args[0])
    bot.xbmc('Player.Seek',{'playerid':pid,'value':t})
  except ValueError:
    return 'Times must be in the format m:ss or h:mm:ss'

@botcmd
def restart(bot,mess,args):
  """start playing again from 0:00"""

  # abort if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  bot.xbmc('Player.Seek',{'playerid':pid,'value':{'seconds':0}})

@botcmd
def hop(bot,mess,args):
  """move forward or back - hop [small|big] [back|forward]"""

  args = ' '.join(args)

  # abort if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

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

  if not args:
    return 'You must specify a URL'

  agent = {'User-agent':'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:46.0) '
      +'Gecko/20100101 Firefox/46.0'}
  msg = args[0]

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

  s = 'Unsupported URL'

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

    # send xbmc request and seek if given custom start time
    result = bot.xbmc('Player.Open',{'item':{'file':
        'plugin://plugin.video.youtube/play/?video_id='+vid}})
    if tim:
      bot.run_cmd('seek',[tim])

    try:
      # retrieve video info from webpage
      api = 'https://youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json'
      j = json.loads(requests.get(api % vid,headers=agent).text)
      title = util.cleanhtml(j['title'])
      channel = util.cleanhtml(j['author_name'])

      # respond to the user with video info
      s = 'Streaming "'+title+'" by "'+channel+'" from YouTube'

    except:
      s = 'Streaming (unable to retrieve title) from YouTube'

    if tim:
      s += (' at '+tim)

  elif 'twitch' in msg.lower():

    # get the webpage
    if 'channel=' in msg:
      vid = msg.split('channel=')[-1].split('&')[0]
    else:
      vid = msg.split('twitch.tv/')[-1].split('/')[0]
    html = requests.get('http://twitch.tv/'+vid,headers=agent).text

    # find the stream title
    stream = html.find("property='og:title'")
    stop = html.rfind("'",0,stream)
    start = html.rfind("'",0,stop)+1
    stream = html[start:stop]

    # find the stream description
    title = html.find("property='og:description'")
    stop = html.rfind("'",0,title)
    start = html.rfind("'",0,stop)+1
    title = html[start:stop]

    response = bot.xbmc('Player.Open',{'item':{'file':
        'plugin://plugin.video.twitch/playLive/'+vid}})
    s = 'Streaming "'+title+'" by "'+stream+'" from Twitch Live'

  bot.last_played = None
  if bot.has_plugin('bookmark'):
    bot.last_resume = None
  return s

@botcmd
def videos(bot,mess,args):
  """open folder as a playlist - videos [include -exclude] [#track] [@match]"""

  if not bot.has_plugin('library'):
    return 'This command not available because plugin "library" not loaded'

  return _files(bot,args,bot.lib_video_dir,1)

@botcmd
def video(bot,mess,args):
  """search and play a single video - video [include -exclude]"""

  if not bot.has_plugin('library'):
    return 'This command not available because plugin "library" not loaded'

  return _file(bot,args,bot.lib_video_file)

@botcmd
def audios(bot,mess,args):
  """open folder as a playlist - audios [include -exclude] [#track] [@match]"""

  if not bot.has_plugin('library'):
    return 'This command not available because plugin "library" not loaded'

  return _files(bot,args,bot.lib_audio_dir,0)

@botcmd
def audio(bot,mess,args):
  """search and play a single audio file - audio [include -exclude]"""

  if not bot.has_plugin('library'):
    return 'This command not available because plugin "library" not loaded'

  return _file(bot,args,bot.lib_audio_file)

@botcmd
def fullscreen(bot,mess,args):
  """control fullscreen - fullscreen [toggle|on|off]"""

  args = ' '.join(args).lower()
  opt = 'toggle'
  if args=='on':
    opt = True
  if args=='off':
    opt = False
  bot.xbmc('GUI.SetFullscreen',{'fullscreen':opt})

@botcmd(name='random')
def random_chat(bot,mess,args):
  """play random song - random [include -exclude]"""

  if not bot.has_plugin('library'):
    return 'This command not available because plugin "library" not loaded'

  # check if a search term was passed
  if not args:
    matches = bot.lib_audio_file
  else:
    matches = util.matches(bot.lib_audio_file,args)

  if len(matches)==0:
    return 'Found 0 matches'

  # play a random audio file from the matches
  rand = random.randint(0,len(matches)-1)
  match = bot.library_translate(matches[rand])

  result = bot.xbmc('Player.Open',{'item':{'file':match}})
  if 'error' in result.keys():
    s = 'Unable to open: '+match
    log.error(s)
    return s

  bot.run_cmd('fullscreen',['on'])

  return 'Playing "'+match+'"'

@botcmd(name='xbmc',ctrl=True)
def xbmc_chat(bot,mess,args):
  """send raw JSON request - xbmc method [params]"""

  if not args:
    return 'http://http://kodi.wiki/view/JSON-RPC_API/v6'

  text = mess.get_text()
  args = text.split(' ')[1:]

  # if specified convert params to a dict
  params = None
  if len(args)>1:
    params = json.loads(' '.join(args[1:]))

  # make the request and check for an error
  result = bot.xbmc(args[0],params)
  if 'error' in result:
    return str(result['error'])
  return str(result['result'])

@botcmd
def shuffle(bot,mess,args):
  """change shuffle - shuffle (check|on|off)"""

  if not args:
    args = ['check']

  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  # set shuffle
  if args[0]=='on':
    bot.xbmc('Player.SetShuffle',{'playerid':pid,'shuffle':True})
    return 'Enabled shuffle'

  if args[0]=='off':
    bot.xbmc('Player.SetShuffle',{'playerid':pid,'shuffle':False})
    return 'Disabled shuffle'

  # return the shuffle status of the current player
  params = {'playerid':pid,'properties':['shuffled']}
  result = bot.xbmc('Player.GetProperties',params)['result']['shuffled']
  if result:
    return 'Shuffle is enabled'
  return 'Shuffle is disabled'

@botfunc
def xbmc(bot,method,params=None,timeout=None):
  """wrapper method to always provide IP to static method"""

  timeout = (timeout or bot.opt('xbmc.timeout'))
  return util.xbmc(bot.opt('xbmc.ip'),method,params,
      bot.opt('xbmc.username'),bot.opt('xbmc.password'),timeout)

@botfunc
def xbmc_active_player(bot,timeout=None):
  """wrapper method to always provide IP to static method"""

  timeout = (timeout or bot.opt('xbmc.timeout'))
  return util.xbmc_active_player(bot.opt('xbmc.ip'),
      bot.opt('xbmc.username'),bot.opt('xbmc.password'),timeout)

def playpause(bot,target):
  """helper function for play() and pause()"""

  # return None if nothing is playing
  active = bot.xbmc_active_player()
  if active is None:
    return 'Nothing playing'
  (pid,typ) = active

  # check player status before sending PlayPause command
  speed = bot.xbmc('Player.GetProperties',
      {'playerid':pid,'properties':["speed"]})
  speed = speed['result']['speed']
  if speed==target:
    bot.xbmc('Player.PlayPause',{"playerid":pid})

def _files(bot,args,dirs,pid):
  """helper function for videos() and audios()"""

  if not args:
    return 'You must specify a search term'
  cmd = ' '.join(args)

  # check for item# as last arg and @ for item match string
  last = args[-1]
  num = None
  search = None

  if last.startswith('@'):
    search = util.get_args(last[1:])
  elif last.startswith('#'):
    try:
      num = int(last[1:])-1
    except ValueError:
      pass

  # default is 0 if not specified
  if (search is not None) or (num is not None):
    args = args[:-1]
  if not search and not num:
    num = 0

  # find matches and respond if len(matches)!=1
  matches = util.matches(dirs,args)

  if len(matches)==0:
    return 'Found 0 matches'

  # default to top dir if every match is a sub dir
  matches = util.reducetree(matches)

  if len(matches)>1:
    maxm = bot.opt('library.max_matches')
    if maxm<1 or len(matches)<=maxm:
      return 'Found '+str(len(matches))+' matches: '+util.list2str(matches)
    else:
      return 'Found '+str(len(matches))+' matches'

  # translate library path if necessary
  match = bot.library_translate(matches[0])

  # if there was 1 match, add the whole directory to a playlist
  # also check for an error opening the directory
  bot.xbmc('Playlist.Clear',{'playlistid':pid})

  result = bot.xbmc('Playlist.Add',{'playlistid':pid,'item':
      {'directory':match}},timeout=60)
  if 'error' in result.keys():
    s = 'Unable to open: '+match
    log.error(s)
    return s

  msg = ''

  # find first item matching @search
  if search:
    params = {'playlistid':pid,'properties':['file']}
    items = bot.xbmc('Playlist.GetItems',params)['result']['items']
    items = [x['file'] for x in items]
    item_matches = util.matches(items,search,False)

    if len(item_matches):
      num = items.index(item_matches[0])
      msg += 'Found matching item "%s" --- ' % os.path.basename(item_matches[0])
    else:
      num = 0
      msg += 'No item matching "%s" --- ' % ' '.join(search)

  bot.xbmc('Player.Open',{'item':{'playlistid':pid,'position':num}})
  bot.run_cmd('fullscreen',['on'])

  # set last_played for bookmarking
  bot.last_played = (pid,matches[0])

  return msg+'Playlist from "'+match+'" starting with #'+str(num+1)

def _file(bot,args,dirs):
  """helper function for video() and audio()"""

  if not args:
    return 'You must specify a search term'

  # find matches and respond if len(matches)!=1
  matches = util.matches(dirs,args)

  if len(matches)==0:
    return 'Found 0 matches'

  if len(matches)>1:
    maxm = bot.opt('library.max_matches')
    if maxm<1 or len(matches)<=maxm:
      return 'Found '+str(len(matches))+' matches: '+util.list2str(matches)
    else:
      return 'Found '+str(len(matches))+' matches'

  # translate library path if necessary
  match = bot.library_translate(matches[0])

  # if there was 1 match, play the file, and check for not found error
  result = bot.xbmc('Player.Open',{'item':{'file':match}})
  if 'error' in result.keys():
    s = 'Unable to open: '+match
    log.error(s)
    return s

  bot.run_cmd('fullscreen',['on'])

  # clear last_played
  bot.last_played = None
  if bot.has_plugin('bookmark'):
    bot.last_resume = None

  return 'Playing "'+match+'"'
