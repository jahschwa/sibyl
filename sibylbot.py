#!/usr/bin/env python
#
# XBMC JSON-RPC XMPP MUC bot

# built-ins
import json,time,os,subprocess,logging

# dependencies
import requests,smbc
from jabberbot import JabberBot,botcmd

class SibylBot(JabberBot):
  """Sibyl is mostly an XBMC bot for friends"""

  def __init__(self,*args,**kwargs):
    """override to only answer direct msgs"""
    
    # required kwargs
    self.rpi_ip = kwargs.get('rpi_ip')
    
    # optional kwargs
    self.nick_name = kwargs.get('nick_name','Sibyl')
    self.audio_dirs = kwargs.get('audio_dirs',[])
    self.video_dirs = kwargs.get('video_dirs',[])
    
    # configure logging
    self.log_file = kwargs.get('log_file','/var/log/sibyl.log')
    logging.basicConfig(filename=self.log_file,format='%(asctime)-15s | %(message)s')
    
    # delete kwargs before calling super init
    for a in ['rpi_ip','nick_name','audio_dirs','video_dirs','log_file']:
      try:
        del kwargs[a]
      except KeyError:
        pass
    
    self.__born = time.time()
    
    # add an additional kwarg for enabling only direct messages
    self.only_direct = kwargs.get('only_direct',False)
    try:
      del kwargs['only_direct']
    except KeyError:
      pass
    
    super(SibylBot,self).__init__(*args,**kwargs)

  def callback_message(self,conn,mess):
    """override to only answer direct msgs"""
    
    # wait 5 seconds before executing commands to account for XMPP MUC history
    # playback since JabberBot and XMPPpy don't let you disable it by
    # modifying the presence stanza
    now = time.time()
    if now<self.__born+5:
      return
    
    # discard blank messages
    msg = mess.getBody()
    if not msg:
      return
    
    # don't respond to messages from myself
    if self.nick_name.lower() in str(mess.getFrom()).lower():
      return
    
    # only respond to direct messages (i.e. those containing NICKNAME)
    if self.only_direct and self.nick_name.lower() in msg.lower():
      mess.setBody(' '.join(msg.split(' ',1)[1:]))
      return super(SibylBot,self).callback_message(conn,mess)

  def unknown_command(self,mess,cmd,args):
    """override unknown command callback"""
    
    return 'Unknown command "'+cmd+'"'

  @botcmd
  def git(self,mess,args):
    """return a link to the github page"""
  
    return 'https://github.com/TheSchwa/sibyl'

  @botcmd
  def hello(self,mess,args):
    """(basic test) reply if someone says hello"""
    
    return 'Hello world!'
  
  @botcmd
  def tv(self,mess,args):
    """pass command to cec-client"""
    
    cmd = ['echo',args+' 0']
    cec = ['cec-client','-s']
    
    # execute echo command and pipe output to PIPE
    p = subprocess.Popen(cmd,stdout=subprocess.PIPE)
    
    # execute cec-client using PIPE as input and sending output to /dev/null
    DEVNULL = open(os.devnull,'wb')
    subprocess.call(cec,stdin=p.stdout,stdout=DEVNULL,close_fds=True)
  
  @botcmd
  def info(self,mess,args):
    """display info about currently playing file"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
    if pid is None:
      return 'Nothing playing'
    
    # get file name
    result = self.xbmc('Player.GetItem',{'playerid':pid})
    name = result['result']['item']['label']
    
    # get speed, current time, and total time
    result = self.xbmc('Player.GetProperties',{'playerid':pid,'properties':['speed','time','totaltime']})
    current = result['result']['time']
    total = result['result']['totaltime']
    
    # translate speed: 0 = 'paused', 1 = 'playing'
    speed = result['result']['speed']
    status = 'playing'
    if speed==0:
      status = 'paused'
    
    playlists = ['Audio','Video','Picture']
    return playlists[pid]+' '+status+' at '+time2str(current)+'/'+time2str(total)+' - "'+name+'"'
  
  @botcmd
  def play(self,mess,args):
    """if xbmc is paused, begin playing again"""
    
    self.playpause(0)
  
  @botcmd
  def pause(self,mess,args):
    """if xbmc is playing, pause it"""
    
    self.playpause(1)
  
  @botcmd
  def stop(self,mess,args):
    """if xbmc is playing, stop it"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
    if pid is None:
      return None

    self.xbmc('Player.Stop',{"playerid":pid})
  
  @botcmd
  def prev(self,mess,args):
    """if xbmc is playing, go to previous in the playlist"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
    if pid is None:
      return None
    
    # the first call goes to 0:00, the second actually goes back in playlist
    self.xbmc('Player.GoTo',{'playerid':pid,'to':'previous'})
    self.xbmc('Player.GoTo',{'playerid':pid,'to':'previous'})

  @botcmd
  def next(self,mess,args):
    """if xbmc is playing, go to next in the playlist"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
    if pid is None:
      return None
    
    self.xbmc('Player.GoTo',{'playerid':pid,'to':'next'})

  @botcmd
  def jump(self,mess,args):
    """jump to a specific number in the playlist"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
    if pid is None:
      return None
    
    # try to parse the arg to an int
    try:
      num = int(args.split(' ')[-1])-1
      self.xbmc('Player.GoTo',{'playerid':pid,'to':num})
      return None
    except ValueError:
      return 'Playlist position must be an integer greater than 0'
  
  @botcmd
  def seek(self,mess,args):
    """go to a specific time in the playing file"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
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
      self.xbmc('Player.Seek',{'playerid':pid,'value':{'hours':h,'minutes':m,'seconds':s}})
    except ValueError:
      return 'Times must be in the format m:ss or h:mm:ss'

  @botcmd
  def restart(self,mess,args):
    """start playing again from the beginning"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
    if pid is None:
      return None
    
    self.xbmc('Player.Seek',{'playerid':pid,'value':{'seconds':0}})

  @botcmd
  def hop(self,mess,args):
    """sibyl hop [small|big] [back|forward]"""
    
    # abort if nothing is playing
    pid = self.xbmc_active_player()
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
    
    self.xbmc('Player.Seek',{'playerid':pid,'value':s})
    return None

  @botcmd
  def stream(self,mess,args):
    """stream a video from [YouTube, Twitch (Live)]"""
    
    msg = mess.getBody()
    
    if 'youtube' in msg:
      
      vid = msg[msg.find('watch?v=')+8:]
      html = requests.get('http://youtube.com/watch?v='+vid).text
      title = html[html.find('<title>')+7:html.find(' - YouTube</title>')]
      
      channel = html.find('class="yt-user-info"')
      start = html.find('>',channel+1)
      start = html.find('>',start+1)+1
      stop = html.find('<',start+1)
      channel = html[start:stop]
      
      response = self.xbmc('Player.Open',{'item':{'file':'plugin://plugin.video.youtube/play/?video_id='+vid}})
      return 'Streaming "'+title+'" by "'+channel+'" from YouTube'
      
    elif 'twitch' in msg:
      
      vid = msg[msg.find('twitch.tv/')+10:]
      html = requests.get('http://twitch.tv/'+vid).text
      
      stream = html.find("property='og:title'")
      stop = html.rfind("'",0,stream)
      start = html.rfind("'",0,stop)+1
      stream = html[start:stop]
      
      title = html.find("property='og:description'")
      stop = html.rfind("'",0,title)
      start = html.rfind("'",0,stop)+1
      title = html[start:stop]
      
      response = self.xbmc('Player.Open',{'item':{'file':'plugin://plugin.video.twitch/playLive/'+vid}})
      return 'Streaming "'+title+'" by "'+stream+'" from Twitch Live'
      
    else:
      return 'Unsupported URL'

  @botcmd
  def videos(self,mess,args):
    """open a folder as a playlist - videos [name] [episode]"""
    
    return self.files(args,self.video_dirs,1)

  @botcmd
  def video(self,mess,args):
    """search for and play a single video"""

    return self.file(args,self.video_dirs)

  @botcmd
  def audios(self,mess,args):
    """open a folder as a playlist - audios [name] [track#]"""
    
    return self.files(args,self.audio_dirs,0)
  
  @botcmd
  def audio(self,mess,args):
    """search for and play a single audio file"""
    
    return self.file(args,self.audio_dirs)

  @botcmd
  def fullscreen(self,mess,args):
    """toggle fullscreen"""
    
    self.xbmc('GUI.SetFullscreen',{'fullscreen':'toggle'})
  
  def xbmc(self,method,params=None):
    """wrapper method to always provide IP to static method"""
    
    return xbmc(self.rpi_ip,method,params)
  
  def xbmc_active_player(self):
    """wrapper method to always provide IP to static method"""
    
    return xbmc_active_player(self.rpi_ip)
  
  def playpause(self,target):
    """helper function for play() and pause()"""
    
    pid = self.xbmc_active_player()
    if pid is None:
      return None

    speed = self.xbmc('Player.GetProperties',{'playerid':pid,'properties':["speed"]})
    speed = speed['result']['speed']
    if speed==target:
      self.xbmc('Player.PlayPause',{"playerid":pid})
  
  def files(self,args,dirs,pid):
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
    matches = self.find('dir',dirs,name)
    if len(matches)==0:
      return 'No matches found'
    elif len(matches)>1:
      return 'Multiple matches: '+str(matches)
    
    # if there was only 1 match, add the whole directory to a playlist
    self.xbmc('Playlist.Clear',{'playlistid':pid})
    self.xbmc('Playlist.Add',{'playlistid':pid,'item':{'directory':matches[0]}})
    self.xbmc('Player.Open',{'item':{'playlistid':pid,'position':num}})
    self.xbmc('GUI.SetFullscreen',{'fullscreen':True})

    return 'Playlist from "'+matches[0]+'" starting at #'+str(num+1)
  
  def file(self,args,dirs):
    """helper function for video() and audio()"""
    
    name = args.split(' ')
    
    # find matches and respond if len(matches)!=1
    matches = self.find('file',dirs,name)
    if len(matches)==0:
      return 'No matches found'
    elif len(matches)>1:
      return 'Multiple matches: '+str(matches)
    
    # if there was only 1 match, play the file
    self.xbmc('Player.Open',{'item':{'file':matches[0]}})
    self.xbmc('GUI.SetFullscreen',{'fullscreen':True})

    return 'Playing "'+matches[0]+'"'
  
  def find(self,fd,dirs,name):
    """helper function for file() and files()"""
    
    paths = []
    smbpaths = []
    
    # sort paths into local and samba based on whether they're tuples
    for path in dirs:
      if isinstance(path,tuple):
        smbpaths.append(path)
      else:
        paths.append(path)
    
    matches = []
    
    # find all matching directories or files depending on fd parameter
    for path in paths:
      try:
        if fd=='dir':
          contents = rlistdir(path)
        else:
          contents = rlistfiles(path)
        for entry in contents:
          try:
            if checkall(name,entry):
              matches.append(entry)
          except UnicodeError:
            self.log.error('Unicode error parsing path "'+entry+'"')
      except OSError:
        self.log.error('Unable to traverse "'+path+'"')
    
    # same as above but for samba shares
    for path in smbpaths:
      try:
        ctx = smbc.Context(auth_fn=path[1])
        if fd=='dir':
          contents = rsambadir(ctx,path[0])
        else:
          contents = rsambafiles(ctx,path[0])
        for entry in contents:
          try:
            if checkall(name,entry):
              matches.append(entry)
          except UnicodeError:
            self.log.error('Unicode error parsing path "'+entry+'"')
      except RuntimeError:
        self.log.error('Unable to traverse "'+path+'"')
    
    return matches

def xbmc(ip,method,params=None):
  """make a JSON-RPC request to xbmc and return the resulti as a dict"""
  
  p = {'jsonrpc':'2.0','id':1,'method':method}
  if params is not None:
    p['params'] = params
  
  url = 'http://'+ip+'/jsonrpc'
  headers = {'content-type':'application/json'}
  payload = p
  params = {'request':json.dumps(payload)}
  r = requests.get(url,params=params,headers=headers)
  
  return json.loads(r.text)

def xbmc_active_player(ip):
  """return the id of the currently active player or None"""
  
  j = xbmc(ip,'Player.GetActivePlayers')
  if len(j['result'])==0:
    return None
  return j['result'][0]['playerid']

def time2str(t):
  """change the time dict to a string"""
  
  s = ''
  hr = str(t['hours'])
  mi = str(t['minutes'])
  sec = str(t['seconds'])
  
  if t['hours']>0:
    s += (hr+':')
    s+= (mi.zfill(2)+':')
  else:
    s+= (mi+':')
  s+= sec.zfill(2)
  
  return s

def rlistdir(path):
  """list folders recursively"""
  
  alldirs = []
  for (cur_path,dirnames,filenames) in os.walk(path):
    for dirname in dirnames:
      alldirs.append(os.path.join(cur_path,dirname))
  return alldirs

def rlistfiles(path):
  """list files recursively"""
  
  allfiles = []
  for (cur_path,dirnames,filenames) in os.walk(path):
    for filename in filenames:
      allfiles.append(os.path.join(cur_path,filename))
  return allfiles

def rsambadir(ctx,path):
  """recursively list directories"""
  
  alldirs = []
  d = ctx.opendir(path)
  contents = d.getdents()
  for c in contents:
    if '(Dir)' in str(c) and c.name!='.' and c.name!='..':
      cur_path = path+'/'+c.name
      alldirs.append(cur_path)
      alldirs.extend(rsambadir(ctx,cur_path))
  return alldirs

def rsambafiles(ctx,path):
  """recursively list files"""
  
  allfiles = []
  d = ctx.opendir(path)
  contents = d.getdents()
  for c in contents:
    cur_path = path+'/'+c.name
    if '(File)' in str(c):
      allfiles.append(cur_path)
    elif '(Dir)' in str(c) and c.name!='.' and c.name!='..':
      allfiles.extend(rsambafiles(ctx,cur_path))
  return allfiles

def checkall(l,s):
  """make sure all strings in l are in s unless they start with '-' """
  
  for x in l:
    if (x[0]!='-') and (x.lower() not in s.lower()):
      return False
    if (x[0]=='-') and (x[1:].lower() in s.lower()):
      return False
  return True
