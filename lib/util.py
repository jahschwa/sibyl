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

import os,requests,json,imp,inspect

# @param s (str) the string to split
# @param sep (str) [' '] the string on which to split
# @return (list) the given string s split at every sep and each item stripped
def split_strip(s,sep=' '):
  """split the string into a list and strip all entries"""

  return [x.strip() for x in s.split(sep)]

# @param fil (str) the file to test
# @param delete (bool) [False] delete the file if it didn't already exist
# @raises (IOError) if the file can't be written
def can_write_file(fil,delete=False):
  """check if we have write permission to the specified file"""

  do_delete = (delete and not os.path.isfile(fil))

  f = open(fil,'a')
  f.close()

  # even just opening the file creates it, so delete it if asked
  if do_delete:
    os.remove(fil)

# @param ip (str) the IP, including port, of XBMC/Kodi/OSMC/etc.
# @param method (str) the JSON-RPC method to call
# @param params (dict) [None] the parameters to use for the method
# @param user (str) [None] the username to login to XBMC's web server
# @param pword (str) [None] the password to login to XBMC's web server
# @return (dict) the response from XBMC
def xbmc(ip,method,params=None,user=None,pword=None,timeout=5):
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
  auth = (user,pword)
  r = requests.get(url,params=params,headers=headers,auth=auth,timeout=timeout)

  # return the response from xbmc as a dict
  return json.loads(r.text)

# @param ip (str) the IP, including port, of XBMC/Kodi/OSMC/etc.
# @param user (str) [None] the username to login to XBMC's web server
# @param pword (str) [None] the password to login to XBMC's web server
# @return (None,tuple of (int,str)) the (playerid,filetype) of the active player
def xbmc_active_player(ip,user=None,pword=None,timeout=5):
  """return the id of the currently active player or None"""

  result = xbmc(ip,'Player.GetActivePlayers',user=user,pword=pword,
      timeout=timeout)['result']
  if len(result)==0:
    return None

  # (somewhat) naively assume there is only one active player at a time
  pid = result[0]['playerid']
  typ = result[0]['type']
  if typ not in ('audio','video'):
    return None

  return (pid,typ)

# @param lib (list) a list of file names to search through
# @param args (list) a list of search terms to match
# @param sort (bool) [True] whether to sort the result
# @return (list) a list of matching file names
def matches(lib,args,sort=True):
  """helper function for search(), files(), and file()"""

  # find matches
  matches = []
  for entry in lib:
    try:
      if checkall(args,entry):
        matches.append(entry)
    except:
      pass

  # sort if asked
  if sort:
    matches = xbmc_sorted(matches)
  return matches

# @param args (str) a command string
# @param lower (bool) [False] whether to lowercase everything
# @return (list) space-separated args
def get_args(args,lower=False):
  """get space-separated args accounting for quotes"""

  l = []
  quote = False
  to_lower = lower
  s = ''
  for c in args:

    # separate on spaces unless inside quotes
    if c==' ':
      if quote:
        s += c
      elif s:
        l.append(s)
        s = ''

    # keep track of quotes
    elif c=='"':
      if quote:
        quote = False
        to_lower = lower
      else:
        quote = True
        to_lower = False

    # add characters to the current string
    else:
      if to_lower:
        s += c.lower()
      else:
        s += c

  # most "args" don't end in a space, so usually we miss the last one
  if s:
    l.append(s)

  return l

# @param t (dict) an XBMC time dict
# @return (str) human-readable time
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

# @param t (int) seconds
# @return (str) human-readable time
def sec2str(t):
  """change the time in seconds to a string"""

  s = int(t)

  h = int(s/3600)
  s -= 3600*h
  m = int(s/60)
  s -= 60*m

  return time2str({'hours':h,'minutes':m,'seconds':s})

# @param t (str) human-readable time
# @return (dict) XBMC time dict
def str2time(t):
  """change the string to a time dict"""

  c1 = t.find(':')
  c2 = t.rfind(':')
  s = int(t[c2+1:])
  h = 0
  if c1==c2:
    m = int(t[:c1])
  else:
    m = int(t[c1+1:c2])
    h = int(t[:c1])

  return {'hours':h,'minutes':m,'seconds':s}

# @param t (dict) XBMC time dict
# @return (int) seconds
def time2sec(t):
  """change the time dict to seconds"""

  return 3600*t['hours']+60*t['minutes']+t['seconds']

# @param t (str) human-readable time
# @return (int) seconds
def str2sec(t):
  """change the string to seconds"""

  return time2sec(str2time(t))

# @param path (str,unicode) a local directory
# @return tuple(list,list) all (dirs,files) in given directory (recursive)
def rlistdir(path,symlinks=True):
  """list folders recursively"""

  dirs = []
  files = []
  for (cur_path,dirnames,filenames) in os.walk(path,followlinks=symlinks):
    for dirname in dirnames:
      dirs.append(os.path.join(cur_path,dirname)+os.path.sep)
    for filename in filenames:
      files.append(os.path.join(cur_path,filename))
  return (dirs,files)

# @param l (list of str) list of search terms
# @param s (str) the string to test against each search term
# @return (bool) True if every string in l matches s
def checkall(l,s):
  """make sure all strings in l are in s unless they start with '-' """

  for x in l:

    # if the test string doesn't start with '-', it must match
    if (x[0]!='-') and (x.lower() not in s.lower()):
      return False

    # if it does start with '-', it must not match
    if (x[0]=='-') and (x[1:].lower() in s.lower()) and (len(x[1:])>0):
      return False
  return True

# @param start (int) index to start searching
# @param page (str) the text of a web page
# @return (tuple of (str,int)) the (cell_conntents,cell_end_index)
def getcell(start,page):
  """return the contents of the next table cell and its end index"""

  # used in the ups command to make life easier
  start = page.find('<td',start+1)
  start = page.find('>',start+1)
  stop = page.find('</td>',start+1)
  s = page[start+1:stop].strip()
  s = s.replace('\n',' ').replace('\t',' ')
  return (' '.join(s.split()),stop)

# @param l (list) the list to convert
# @return (str) the list with each item on a new line
def list2str(l):
  """return the list on separate lines"""

  # makes match lists look much better in chat or pastebin
  return '\n'+'\n'.join(l)

# @param paths (list) file paths to reduce
# @return (list) the input, or a basedir shared by all paths
def reducetree(paths):
  """if all paths are sub-dirs of a common root, return the root"""

  # if all paths are sub-dirs, the shortest is guaranteed to contain it
  shortest = sorted(paths,key=len)[0]
  parent = None

  # also check for the parent directory of the shortest path
  if ((shortest.startswith('smb://') and len(shortest.split('/'))>5)
      or (not shortest.startswith('smb://') and shortest!='/')):
    parent = shortest[:shortest.rfind('/',0,-1)+1]

  # check all paths to see if they contain either the shortest or its parent
  short = True
  par = (parent is not None)
  for path in paths:
    short = (short and path.startswith(shortest))
    par = (par and path.startswith(parent))

  # prioritize the shortest over the parent
  if short:
    return [shortest]
  if par:
    return [parent]
  return paths

# @param text (str)
# @return (str) the input with common html characters decoded
def cleanhtml(text):
   """replace common html codes with actual characters"""

   codes = {'&#39;'  : "'",
            '&amp;'  : '&',
            '&quot;' : '"'}

   for code in codes:
     text = text.replace(code,codes[code])

   return text

# @param name (str) the name of the file to load as a module (don't include .py)
# @param path (str) the directory to search for the file
# @return (module) the loaded module
def load_module(name,path):
  """return the loaded module after closing the file"""

  found = imp.find_module(name,[path])
  try:
    return imp.load_module(name,*found)
  finally:
    found[0].close()

# @param name (str) name of a module to check
# @return (bool) True if the module exists
def has_module(name):
  """return True if the module exists"""

  try:
    imp.find_module(name)
    return True
  except ImportError:
    return False

# @param s (str) string to test for being a number
# @return (bool) whether the string is a valid integer
def is_int(s):
  """check if the given string is an integer"""

  try:
    int(s)
    return True
  except:
    return False

# @param files (list of str) a list of file paths
# @return (list) the input sorted as XBMC default sort
def xbmc_sorted(files):
  """sort a list of files as xbmc does (i think) so episodes are correct"""

  return sorted(files,cmp=xbmc_cmp)

# @param a (str) a string to compare
# @param b (str) a string to compare
# @return (int) -1 or 1 depending on which input should come first
def xbmc_cmp(a,b):
  """compare function for xbmc_sort"""

  a = a.lower()
  b = b.lower()
  if a==b:
    return 0
  ia = 0
  ib = 0
  while ia<len(a) and ib<len(b):

    # if both characters are numbers, read until the numbers stop
    if a[ia].isdigit() and b[ib].isdigit():
      astr = ''
      bstr = ''
      while ia<len(a) and a[ia].isdigit():
        astr += a[ia]
        ia += 1
      while ib<len(b) and b[ib].isdigit():
        bstr += b[ib]
        ib += 1

      # sort episodes correctly (e.g. 2 is before 10)
      if astr!=bstr:
        return (1 if int(astr)-int(bstr)>0 else -1)
    elif a[ia]!=b[ib]:
      return (1 if a[ia]>b[ib] else -1)
    ia += 1
    ib += 1
  return (1 if len(a)<len(b) else -1)

# @param (int) [2] the number of steps to go back in the stack; you generally
#        don't want 0 (this file) or 1 (the file that called this function)
# @return (str) the module name of the caller's caller
def get_caller(lvl=2):
  """can be called from inside foo() to return the file that called foo()"""

  return os.path.basename(inspect.stack()[lvl][1]).split('.')[0]

# @param s (str,unicode) the string to convert
# @param esc (bool) if True, escape to html char codes; else unescape
# @return (str,unicode) the input but safe for html
def html(s,esc=True):
  """escape characters that break html parsing"""

  chars = { '&':'&amp;', '"':'&quot;', "'":'&#039;', '<':'&lt;', '>':'&gt;'}
  if not esc:
    chars = {v:k for (k,v) in chars.items()}

  for (k,v) in chars.items():
    s = s.replace(k,v)

  return s
