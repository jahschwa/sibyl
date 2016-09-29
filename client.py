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

import sys,socket,select,argparse,time,traceback
from threading import Thread,Event
from Queue import Queue

try:
  import readline
except:
  pass

USER = 'human@socket'
SIBYL = 'sibyl@socket'

def main():

  parser = argparse.ArgumentParser()
  parser.add_argument('-n',default='localhost:8767',help='host:port to connect to',metavar='HOST')
  parser.add_argument('-t',action='store_true',help='include time stamps')
  args = parser.parse_args()

  if ':' not in args.n:
    args.n += ':8767'
  (host,port) = args.n.split(':')
  port = int(port)

  sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
  sock.connect((host,port))

  send_queue = Queue()
  event_close = Event()

  BufferThread(send_queue,event_close,args.t).start()
  SocketThread(sock,send_queue,event_close,args.t).start()

  try:
    while not event_close.is_set():
      time.sleep(1)
  except BaseException as e:
    print traceback.format_exc(e)
    sock.close()

################################################################################
# SocketThread class                                                           #
################################################################################

class SocketThread(Thread):

  def __init__(self,s,q,c,t):
    """create a new thread that reads from stdin and appends to a Queue"""

    super(SocketThread,self).__init__()
    self.daemon = True

    self.buffer = ''

    self.socket = s
    self.queue = q
    self.event_close = c
    self.time = t

  def run(self):
    """receive and send data on the socket"""

    while not self.event_close.is_set():
      (read,write,err) = select.select([self.socket],[self.socket],[],1)

      if self.socket in read:
        try:
          msgs = self.get_msgs()
        except:
          break
        for msg in msgs:
          self.nice_print(msg)

      if self.socket in write:
        while not self.queue.empty():
          self.send_msg(self.queue.get())

      time.sleep(0.1)

    self.socket.close()
    print '\n\nRemote closed connection\n'
    self.event_close.set()

  def get_msgs(self):

    msgs = []
    while self.buffer or not msgs:
      msgs.append(self.get_msg())
    return msgs

  def get_msg(self):

    msg = self.buffer
    while ' ' not in msg:
      s = self.socket.recv(4096)
      if not s:
        raise RuntimeError
      msg += s

    length_str = msg.split(' ')[0]
    target = len(length_str)+1+int(length_str)
    while len(msg)<target:
      msg += self.socket.recv(min(target-len(msg),4096))

    self.buffer = msg[target:]
    return msg[msg.find(' ')+1:]

  def send_msg(self,msg):

    length_str = str(len(msg))
    msg = (length_str+' '+msg)
    target = len(msg)

    sent = 0
    while sent<target:
      sent += self.socket.send(msg[sent:])

  def nice_print(self,s):

    prompt = ((time.asctime()+' | ') if self.time else '')+USER+': '
    spaces = len(readline.get_line_buffer())+len(prompt)
    sys.stdout.write('\r'+' '*spaces+'\r')
    print ((time.asctime()+' | ') if self.time else '')+SIBYL+': '+s
    sys.stdout.write(prompt+readline.get_line_buffer())
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
