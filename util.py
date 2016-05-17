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

  result = xbmc(ip,'Player.GetActivePlayers',user=user,pword=pword)['result']
  if len(result)==0:
    return None

  pid = result[0]['playerid']
  typ = result[0]['type']
  if typ not in ('audio','video'):
    return None
  
  return (pid,typ)

def matches(lib,args,sort=True):
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

  if sort:
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

def rsambadir(ctx,path):
  """recursively list directories"""
  
  alldirs = []
  d = ctx.opendir(path)
  contents = d.getdents()
  for c in contents:
    if '(Dir)' in str(c) and c.name!='.' and c.name!='..':
      cur_path = path+'/'+c.name
      alldirs.append(cur_path+'/')
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
  parent = None
  # also check for the parent directory of the shortest path
  if ((shortest.startswith('smb://') and len(shortest.split('/'))>5)
      or (not shortest.startswith('smb://') and shortest!='/')):
    parent = shortest[:shortest.rfind('/',0,-1)+1]

  short = True
  par = (parent is not None)
  for path in paths:
    short = (short and path.startswith(shortest))
    par = (par and path.startswith(parent))

  if short:
    return [shortest]
  if par:
    return [parent]
  return paths

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
    return imp.load_module(name,*found)
  finally:
    found[0].close()

def xbmc_sorted(files):
  """sort a list of files as xbmc does (i think) so episodes are correct"""
  
  return sorted(files,cmp=xbmc_cmp)

def xbmc_cmp(a,b):
  """compare function for xbmc_sort"""

  a = a.lower()
  b = b.lower()
  if a==b:
    return 0
  ia = 0
  ib = 0
  while ia<len(a) and ib<len(b):
    if a[ia].isdigit() and b[ib].isdigit():
      astr = ''
      bstr = ''
      while a[ia].isdigit():
        astr += a[ia]
        ia += 1
      while b[ib].isdigit():
        bstr += b[ib]
        ib += 1
      if astr!=bstr:
        return int(astr)-int(bstr)
    if a[ia]!=b[ib]:
      return (1 if a[ia]>b[ib] else -1)
    ia += 1
    ib += 1
  return (1 if len(a)<len(b) else -1)
