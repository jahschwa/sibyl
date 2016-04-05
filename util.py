#!/usr/bin/env python

import os,requests,json,imp

def split_strip(s,sep=' '):
  """split the string into a list and strip all entries"""

  return [x.strip() for x in s.split(sep)]

def can_write_file(fil,delete=False):
  """check if we have write permission to the specified file"""

  do_delete = (delete and not os.path.isfile(fil))
  
  f = open(fil,'a')
  f.close()
  
  if do_delete:
    os.remove(fil)

def xbmc(ip,method,params=None,user=None,pword=None):
  """make a JSON-RPC request to xbmc and return the resulti as a dict
  or None if ConnectionError or Timeout"""

  # build a json call with the requests library
  p = {'jsonrpc':'2.0','id':1,'method':method}
  if params is not None:
    p['params'] = params

  url = 'http://'+ip+'/jsonrpc'
  headers = {'content-type':'application/json'}
  payload = p
  params = {'request':json.dumps(payload)}

  r = requests.get(url,params=params,headers=headers,auth=(user,pword),timeout=60)
  # return the response from xbmc as a dict
  return json.loads(r.text)

def xbmc_active_player(ip,user=None,pword=None):
  """return the id of the currently active player or None"""

  j = xbmc(ip,'Player.GetActivePlayers',user=user,pword=pword)
  if len(j['result'])==0:
    return None
  return j['result'][0]['playerid']

def matches(lib,args):
  """helper function for search(), files(), and file()"""

  # implement quote blocking
  name = []
  quote = False
  s = ''
  for arg in args:
    if arg.startswith('"') and arg.endswith('"'):
      name.append(arg[1:-1])
    elif arg.startswith('"'):
      quote = True
      s += arg[1:]
    elif arg.endswith('"'):
      quote = False
      s += (' '+arg[:-1])
      name.append(s)
      s = ''
    elif quote:
      s += (' '+arg)
    else:
      name.append(arg)
  if quote:
    name.append(s.replace('"',''))

  # find matches
  matches = []
  for entry in lib:
    try:
      if checkall(name,entry):
        matches.append(entry)
    except:
      pass
  matches.sort()
  return matches

def time2str(t):
  """change the time dict to a string"""

  # based on the format returned by xbmc's json api
  s = ''
  hr = str(t['hours'])
  mi = str(t['minutes'])
  sec = str(t['seconds'])

  # only include hours if they exist
  if t['hours']>0:
    s += (hr+':')
    s+= (mi.zfill(2)+':')
  else:
    s+= (mi+':')
  s+= sec.zfill(2)

  return s

def sec2str(t):
  """change the time in seconds to a string"""

  s = int(t)

  h = int(s/3600)
  s -= 3600*h
  m = int(s/60)
  s -= 60*m

  return time2str({'hours':h,'minutes':m,'seconds':s})

def rlistdir(path):
  """list folders recursively"""

  alldirs = []
  for (cur_path,dirnames,filenames) in os.walk(path):
    for dirname in dirnames:
      alldirs.append(os.path.join(cur_path,dirname)+'/')
  return alldirs

def rlistfiles(path):
  """list files recursively"""

  allfiles = []
  for (cur_path,dirnames,filenames) in os.walk(path):
    for filename in filenames:
      allfiles.append(os.path.join(cur_path,filename))
  return allfiles

def rsambadir(smb,path):
  """recursively list directories"""

  alldirs = []
  items = smb.listdir(path)
  for item in items:
    cur_path = os.path.join(path,item)
    if smb.isdir(cur_path):
      alldirs.append(str('smb:'+smb.path+cur_path)+'/')
      alldirs.extend(rsambadir(smb,cur_path))
  return alldirs

def rsambafiles(smb,path):
  """recursively list files"""

  allfiles = []
  items = smb.listdir(path)
  for item in items:
    cur_path = os.path.join(path,item)
    if smb.isfile(cur_path):
      allfiles.append(str('smb:'+smb.path+cur_path))
    elif smb.isdir(cur_path):
      allfiles.extend(rsambafiles(smb,cur_path))
  return allfiles

def checkall(l,s):
  """make sure all strings in l are in s unless they start with '-' """

  for x in l:
    if (x[0]!='-') and (x.lower() not in s.lower()):
      return False
    if (x[0]=='-') and (x[1:].lower() in s.lower()) and (len(x[1:])>0):
      return False
  return True

def getcell(start,page):
  """return the contents of the next table cell and its end index"""

  # used in the ups command to make life easier
  start = page.find('<td',start+1)
  start = page.find('>',start+1)
  stop = page.find('</td>',start+1)
  s = page[start+1:stop].strip()
  s = s.replace('\n',' ').replace('\t',' ')
  return (' '.join(s.split()),stop)

def list2str(l):
  """return the list on separate lines"""

  # makes match lists look much better in chat or pastebin
  s = '['
  for x in l:
    s += ('"'+x+'",\n')
  return (s[:-2]+']')

def reducetree(paths):
  """if all paths are sub-dirs of a common root, return the root"""

  shortest = sorted(paths,key=len)[0]
  for path in paths:
    if not path.startswith(shortest):
      return paths
  return [shortest]

def cleanhtml(text):
   """replace common html codes with actual characters"""
   
   codes = {'&#39;'  : "'",
            '&amp;'  : '&',
            '&quot;' : '"'}
   
   for code in codes:
     text = text.replace(code,codes[code])
   
   return text

def load_module(name,path):
  """return the loaded module after closing the file"""

  found = imp.find_module(name,[path])
  try:
    mod = imp.load_module(name,*found)
  finally:
    found[0].close()
