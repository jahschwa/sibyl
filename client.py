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

import sys,socket,select,argparse,time,traceback,getpass,ssl
from threading import Thread,Event
from Queue import Queue

USER = 'human@socket'
SIBYL = 'sibyl@socket'

def main():

  parser = argparse.ArgumentParser()
  parser.add_argument('-n','--host',default='localhost:8767',help='host:port to connect to',metavar='HOST')
  parser.add_argument('-t','--timestamp',action='store_true',help='include time stamps')
  parser.add_argument('-p','--password',action='store_true',help='prompt for password')
  parser.add_argument('-v','--noverify',action='store_true',help="don't verify remote certificate")
  parser.add_argument('-s','--ssl',action='store_true',help='use ssl')
  parser.add_argument('-r','--noreadline',action='store_true',help="don't use GNU readline")
  args = parser.parse_args()

  if not args.noreadline:
    try:
      import readline
    except:
      pass

  if args.noverify and not args.ssl:
    print '  *** Ignoring option --noverify (not using ssl)'

  if ':' not in args.host:
    args.host += ':8767'
  (host,port) = args.host.split(':')
  port = int(port)

  pword = None
  if args.password:
    print ''
    pword = getpass.getpass()
    print ''

  sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

  if args.ssl:
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    if not args.noverify:
      context.verify_mode = ssl.CERT_REQUIRED
      context.check_hostname = True
      context.load_default_certs()
    context.options |= (ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3)
    sock = context.wrap_socket(sock,server_hostname=host)
    try:
      sock.connect((host,port))
    except ssl.SSLEOFError:
      print '  *** SSL handshake failed; does the server support it?\n'
      sock.close()
      sys.exit(0)
    except ssl.SSLError as e:
      print ' ***SSL failed because: %s\n' % e.reason
      if e.reason=='CERTIFICATE_VERIFY_FAILED':
        print 'If the server certificate is self-signed, try again with -v\n'
      sys.exit(0)
  else:
    sock.connect((host,port))

  send_queue = Queue()
  event_close = Event()

  BufferThread(send_queue,event_close,args.timestamp).start()
  SocketThread(sock,send_queue,event_close,args.timestamp,pword).start()

  try:
    while not event_close.is_set():
      time.sleep(1)
  except KeyboardInterrupt:
    print '\n'
  except BaseException as e:
    print traceback.format_exc(e)
  sock.close()

################################################################################
# SocketThread class                                                           #
################################################################################

class SocketThread(Thread):

  MSG_AUTH = '0'
  MSG_TEXT = '1'

  AUTH_OKAY = 'OKAY'
  AUTH_FAILED = 'FAILED'
  AUTH_NONE = 'NONE'

  def __init__(self,s,q,c,t,p):
    """create a new thread that reads from stdin and appends to a Queue"""

    super(SocketThread,self).__init__()
    self.daemon = True
    self.auth_sent = False

    self.buffer = ''

    self.socket = s
    self.queue = q
    self.event_close = c
    self.time = t
    self.password = p

  def run(self):
    """receive and send data on the socket"""

    if self.password:
      self.do_auth()
    self.send_msg(' ')

    while not self.event_close.is_set():
      (read,write,err) = select.select([self.socket],[self.socket],[],1)

      if self.socket in read:
        try:
          msgs = self.get_msgs()
        except:
          break
        for msg in msgs:
          if msg:
            self.nice_print(msg)

      if self.socket in write:
        while not self.queue.empty():
          self.send_msg(self.queue.get())

      time.sleep(0.1)

  def die(self,msg):

    self.socket.close()
    print '\n\n  *** '+msg+'\n'
    self.event_close.set()

  def get_msgs(self):

    msgs = []
    while self.buffer or not msgs:
      (typ,msg) = self.get_msg()
      if typ==SocketThread.MSG_AUTH:
        self.check_auth(msg)
        msgs.append(None)
      elif typ==SocketThread.MSG_TEXT or typ is None:
        msgs.append(msg)
      else:
        self.die('Unsupported msg type "%s"; closing connection' % typ)

    return msgs

  def get_msg(self):

    msg = self.buffer
    while ' ' not in msg:
      s = self.socket.recv(4096)
      if not s:
        self.die('Remote closed connection')
        return (None,None)
      msg += s

    length_str = msg.split(' ')[0]
    target = len(length_str)+1+int(length_str)
    while len(msg)<target:
      msg += self.socket.recv(min(target-len(msg),4096))

    (msg,self.buffer) = (msg[:target],msg[target:])
    msg = msg[msg.find(' ')+1:]
    return (msg[0],msg[2:])

  def do_auth(self):

    self.send_msg(self.password,SocketThread.MSG_AUTH)
    self.auth_sent = True

  def check_auth(self,msg):

    if not self.auth_sent:
      self.die('Server requires a password')
      return

    if msg==SocketThread.AUTH_OKAY:
      return
    elif msg==SocketThread.AUTH_FAILED:
      self.die('Invalid username/password')
    elif msg==SocketThread.AUTH_NONE:
      self.nice_print('NOTICE: Server does not require a password')
    else:
      self.die('Received invalid Auth response from server')

  def send_msg(self,msg,typ=None):

    typ = typ or SocketThread.MSG_TEXT
    msg = typ+' '+msg
    length_str = str(len(msg))
    msg = (length_str+' '+msg)
    target = len(msg)

    sent = 0
    while sent<target:
      sent += self.socket.send(msg[sent:])

  def nice_print(self,s):

    prompt = ((time.asctime()+' | ') if self.time else '')+USER+': '
    text = ((time.asctime()+' | ') if self.time else '')+SIBYL+': '+s

    if 'readline' in sys.modules:
      spaces = len(readline.get_line_buffer())+len(prompt)
      sys.stdout.write('\r'+' '*spaces+'\r')
      print text
      sys.stdout.write(prompt+readline.get_line_buffer())
    else:
      sys.stdout.write('\n'+text+'\n'+prompt)

    sys.stdout.flush()

################################################################################
# BufferThread class                                                           #
################################################################################

class BufferThread(Thread):

  def __init__(self,q,c,t):
    """create a new thread that reads from stdin and appends to a Queue"""

    super(BufferThread,self).__init__()
    self.daemon = True

    self.queue = q
    self.event_close = c
    self.time = t

  def run(self):
    """read from stdin, add to the queue, set the event_data Event"""

    while not self.event_close.is_set():
      sys.stdout.write(((time.asctime()+' | ') if self.time else '')+USER+': ')
      s = raw_input()
      self.queue.put(s)

if __name__=='__main__':
  main()
