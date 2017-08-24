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
###############################################################################

import sys,socket,select,argparse,time,traceback,getpass,ssl
from threading import Thread,Event
from Queue import Queue

readline = None

try:
  from PyQt5 import QtGui,QtCore,QtWidgets
  from PyQt5.Qt import QApplication
except:
  pass

USER = 'human@socket'
SIBYL = 'sibyl@socket'

def main():

  parser = argparse.ArgumentParser()
  parser.add_argument('-n','--host',
      default='localhost:8767',
      help='host:port to connect to',
      metavar='HOST')
  parser.add_argument('-t','--timestamp',
      action='store_true',
      help='include time stamps')
  parser.add_argument('-p','--password',
      default=None,const='',nargs='?',
      help='prompt for password')
  parser.add_argument('-v','--noverify',
      action='store_true',
      help="don't verify remote certificate")
  parser.add_argument('-s','--ssl',
      action='store_true',
      help='use ssl')
  parser.add_argument('-r','--noreadline',
      action='store_true',
      help="don't use GNU readline")
  parser.add_argument('-e','--execute',
      default=None,const='',nargs='?',
      help='execute a single command and return')
  parser.add_argument('-g','--gui',
      action='store_true',
      help='start the GUI instead of CLI')
  parser.add_argument('-d','--debug',
      action='store_true',
      help='print debug info (depends -d)')
  parser.add_argument('-w','--timeout',
      default=15,type=int,
      help='timeout in sec (depends -d)')
  args = parser.parse_args()

  if (not args.gui) and (not args.noreadline and (args.execute is None)):
    try:
      import readline as temp
      global readline
      readline = temp
    except:
      pass

  if args.execute is not None:
    Shell(args).run()
  elif args.gui:
    app = QtWidgets.QApplication(sys.argv)
    chat = ChatBox(args)
    chat.log('Ready')
    sys.exit(app.exec_())
  else:
    CLI(args).run()

###############################################################################
# One-off shell command class
###############################################################################

class TimeoutError(Exception):
  pass

class Shell(object):

  def __init__(self,args):

    self.args = args
    self.send_queue = Queue()
    self.event_close = Event()
    self.pword = self.args.password
    self.delim = 'DONE_%s_%s' % (time.time(),hash(time.time()))
    self.response = []
    self.errors = False

  def run(self):

    socket = SocketThread(self)
    socket.connect()
    socket.start()

    cmd = self.args.execute or sys.stdin.read()
    self.send_queue.put(cmd)
    self.send_queue.put('echo '+self.delim)
    start = time.time()

    try:
      while (not self.response
          or self.delim not in [x[1] for x in self.response]):
        if time.time()-start>self.args.timeout:
          raise TimeoutError
        time.sleep(0.1)
    except TimeoutError:
      self.error('Timed out waiting for response.')
    except KeyboardInterrupt:
      pass
    except BaseException as e:
      print traceback.format_exc(e)

    self.event_close.set()
    if socket.is_alive():
      socket.join()

    for (err,s) in self.response:
      if err:
        sys.stderr.write(s+'\n')
        sys.stderr.flush()
      elif s!=self.delim:
        print s

    if self.errors:
      sys.exit(1)

  def say(self,s):

    self.response.append((False,s))

  def log(self,txt):

    if self.args.debug:
      self.response.append((True,'  --- '+txt))

  def error(self,txt):

    self.response.append((True,'  ### '+txt))
    self.errors = True
    self.response.append((False,self.delim))

################################################################################
# CLI class
################################################################################

class CLI(object):

  def __init__(self,args):

    self.args = args
    self.send_queue = Queue()
    self.event_close = Event()

  def run(self):

    self.pword = self.get_pass()

    socket = SocketThread(self)
    socket.connect()
    socket.start()

    time.sleep(1)
    print ''
    BufferThread(self).start()

    try:
      while not self.event_close.is_set():
        time.sleep(0.1)
    except (KeyboardInterrupt,SystemExit):
      pass
    except BaseException:
      print traceback.format_exc(e)

    self.event_close.set()
    if socket.is_alive():
      socket.join()

  def say(self,s):

    prompt = ((time.asctime()+' | ') if self.args.timestamp else '')+USER+': '
    text = ((time.asctime()+' | ') if self.args.timestamp else '')+SIBYL+': '+s

    if 'readline' in sys.modules:
      spaces = len(readline.get_line_buffer())+len(prompt)
      sys.stdout.write('\r'+' '*spaces+'\r')
      print text
      sys.stdout.write(prompt+readline.get_line_buffer())
    else:
      sys.stdout.write('\n'+text+'\n'+prompt)

    sys.stdout.flush()

  def log(self,txt):

    print '  --- '+txt

  def error(self,txt):

    print '  ### '+txt
    sys.exit(0)

  def get_pass(self):

    if self.args.password is None:
      return None
    print ''
    pword = getpass.getpass()
    print ''
    return pword

################################################################################
# SocketThread class
################################################################################

class SocketThread(Thread):

  MSG_AUTH = '0'
  MSG_TEXT = '1'

  AUTH_OKAY = 'OKAY'
  AUTH_FAILED = 'FAILED'
  AUTH_NONE = 'NONE'

  def __init__(self,chat):
    """create a new thread that reads from stdin and appends to a Queue"""

    super(SocketThread,self).__init__()
    self.daemon = True
    self.auth_sent = False

    self.chat = chat
    self.buffer = ''

  def connect(self):

    success = False

    if self.chat.args.noverify and not self.chat.args.ssl:
      self.chat.log('Ignoring option --noverify (not using ssl)')

    host = self.chat.args.host
    if ':' not in host:
      self.chat.log('No port specified; using default 8767')
      host += ':8767'
    (host,port) = host.split(':')
    port = int(port)
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

    if self.chat.args.ssl:
      context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
      if not self.chat.args.noverify:
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        context.load_default_certs()
      context.options |= (ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3)
      sock = context.wrap_socket(sock,server_hostname=host)
      try:
        sock.connect((host,port))
        self.chat.log('SSL Successful')
        success = True
      except ssl.SSLEOFError:
        sock.close()
        self.chat.error('SSL handshake failed; does the server support it?')
      except ssl.SSLError as e:
        if e.reason=='CERTIFICATE_VERIFY_FAILED':
          self.chat.log('If the server certificate is self-signed, '
              + 'try again with -v')
        self.chat.error('SSL failed because: %s' % e.reason)
      except socket.error as e:
        self.chat.error('Socket error: %s' % e.strerror)
    else:
      try:
        sock.connect((host,port))
        success = True
      except socket.error as e:
        self.chat.error('Socket error: %s' % e.strerror)

    if success:
      self.sock = sock
      self.chat.log('Connected')

    return success

  def run(self):
    """receive and send data on the socket"""

    if self.chat.pword:
      self.do_auth()
    self.send_msg(' ')

    while not self.chat.event_close.is_set():
      (read,write,err) = select.select([self.sock],[self.sock],[],1)

      if self.sock in read:
        try:
          msgs = self.get_msgs()
        except:
          self.chat.error('EXCEPTION\n\n'+traceback.format_exc())
          break
        for msg in msgs:
          if msg:
            self.chat.say(msg)

      if self.sock in write:
        while not self.chat.send_queue.empty():
          self.send_msg(self.chat.send_queue.get())

      time.sleep(0.1)

    try:
      self.sock.shutdown(socket.SHUT_RDWR)
    except:
      pass
    self.sock.close()
    self.chat.log('Disconnected')

  def die(self,msg):

    self.chat.event_close.set()
    self.chat.error(msg)

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
      s = self.sock.recv(4096)
      if not s:
        self.die('Remote closed connection')
        return (None,None)
      msg += s

    length_str = msg.split(' ')[0]
    target = len(length_str)+1+int(length_str)
    while len(msg)<target:
      msg += self.chat.sock.recv(min(target-len(msg),4096))

    (msg,self.buffer) = (msg[:target],msg[target:])
    msg = msg[msg.find(' ')+1:]
    return (msg[0],msg[2:])

  def do_auth(self):

    self.send_msg(self.chat.pword,SocketThread.MSG_AUTH)
    self.auth_sent = True

  def check_auth(self,msg):

    if not self.auth_sent:
      self.die('Server requires a password')
      return

    if msg==SocketThread.AUTH_OKAY:
      self.chat.log('Authenticated')
    elif msg==SocketThread.AUTH_FAILED:
      self.die('Invalid password')
    elif msg==SocketThread.AUTH_NONE:
      self.chat.log('Server does not require a password')
    else:
      self.die('Received invalid Auth response from server')

  def send_msg(self,msg,typ=None):

    typ = typ or SocketThread.MSG_TEXT
    msg = typ+' '+msg
    length_str = str(len(msg))
    msg = unicode(length_str+' '+msg).encode('utf8')
    target = len(msg)

    sent = 0
    while sent<target:
      sent += self.sock.send(msg[sent:])

################################################################################
# BufferThread class
################################################################################

class BufferThread(Thread):

  def __init__(self,chat):
    """create a new thread that reads from stdin and appends to a Queue"""

    super(BufferThread,self).__init__()
    self.daemon = True

    self.chat = chat

  def run(self):
    """read from stdin, add to the queue, set the event_data Event"""

    while not self.chat.event_close.is_set():
      s = ((time.asctime()+' | ') if self.chat.args.timestamp else '')+USER+': '
      sys.stdout.write(s)
      s = raw_input()
      self.chat.send_queue.put(s)

################################################################################
# Qt signal bridge class
################################################################################

if 'QtCore' in locals():
  class QtSocketThread(QtCore.QObject):

    sig_say = QtCore.pyqtSignal(str)
    sig_log = QtCore.pyqtSignal(str)
    sig_err = QtCore.pyqtSignal(str)

    def __init__(self,gui):

      super(QtSocketThread,self).__init__()
      self.gui = gui
      self.args = gui.args
      self.pword = gui.pword

      self.send_queue = Queue()
      self.event_close = Event()
      self.socket = SocketThread(self)

    def connect(self):
      return self.socket.connect()

    def run(self):
      self.socket.run()

    def say(self,txt):
      self.sig_say.emit(txt)

    def log(self,txt):
      self.sig_log.emit(txt)

    def error(self,txt):
      self.sig_err.emit(txt)

################################################################################
# Qt GUI class
################################################################################

if 'QtGui' in locals():
  class ChatBox(QtWidgets.QMainWindow):

    def __init__(self,args):

      super(ChatBox,self).__init__()
      self.args = args
      self.pword = ''
      self.connected = False

      self.worker = None
      self.thread = None

      self.initUI()
      self.center()
      self.show()

    def initUI(self):
      """create the main window UI including callbacks"""

      # create a file menu and add options to it
      menu = self.menuBar().addMenu('&Chat')
      self.make_item(menu,'Connect','Ctrl+N')
      self.make_item(menu,'Reconnect','Ctrl+R')
      self.make_item(menu,'Disconnect','Ctrl+D')
      self.make_item(menu,'Copy HTML','Ctrl+H')
      self.make_item(menu,'Copy Plaintext','Ctrl+P')
      self.make_item(menu,'Quit','Ctrl+Q')

      # create the main grid where the buttons will be located
      grid = QtWidgets.QGridLayout()
      grid.setSpacing(10)
      area = QtWidgets.QWidget(self)
      area.setLayout(grid)
      self.setCentralWidget(area)

      # add text boxes for chat
      self.chatpane = QtWidgets.QTextEdit()
      self.chatpane.setReadOnly(True)
      self.chatpane.setMinimumSize(500,200)
      self.chatpane.resize(500,200)
      grid.addWidget(self.chatpane,0,0)

      self.editpane = QtWidgets.QTextEdit()
      self.editpane.setMinimumSize(500,50)
      self.editpane.setMaximumHeight(50)
      self.editpane.resize(500,50)
      self.editpane.textChanged.connect(self.cb_text)
      grid.addWidget(self.editpane,1,0)

      # set title, size, focus
      self.setWindowTitle('Sibyl Socket Chat')
      self.setFocus()

    def make_item(self,menu,name,shortcut):
      """helper function to create a menu item and add it to the menu"""

      item = QtWidgets.QAction(name,self)
      item.setShortcut(QtGui.QKeySequence(shortcut))
      item.triggered.connect(self.cb_menu)
      menu.addAction(item)
      self.addAction(item)

    def center(self):
      """center the window on the current monitor"""

      # http://stackoverflow.com/a/20244839/2258915

      fg = self.frameGeometry()
      cursor = QtWidgets.QApplication.desktop().cursor().pos()
      screen = QtWidgets.QApplication.desktop().screenNumber(cursor)
      cp = QtWidgets.QApplication.desktop().screenGeometry(screen).center()
      fg.moveCenter(cp)
      self.move(fg.topLeft())

    def cb_menu(self):
      """handle menu item presses"""

      t = self.sender().text()
      if t=='Connect':
        cd = ConnectDialog(self)
        if cd.exec_():
          (self.args.host,self.pword,self.args.ssl,self.args.noverify) = cd.get()
          self.start_thread()
      elif t=='Reconnect':
        self.start_thread()
      elif t=='Disconnect':
        if self.worker:
          self.worker.event_close.set()
          self.connected = False
      elif t=='Copy HTML':
        QApplication.clipboard().setText(self.chatpane.toHtml())
      elif t=='Copy Plaintext':
        QApplication.clipboard().setText(self.chatpane.toPlainText())
      elif t=='Quit':
        QtWidgets.qApp.quit()

    def cb_text(self):
      """handle typing and send on enter"""

      text = str(self.editpane.toPlainText())
      if '\n' in text:
        if self.connected:
          text = text.replace('\n','')
          if text:
            self.said(text)
            self.worker.send_queue.put(text)
          self.editpane.clear()
        else:
          self.editpane.textCursor().deletePreviousChar()

    def start_thread(self):

      worker = QtSocketThread(self)
      thread = QtCore.QThread(self)
      worker.moveToThread(thread)
      thread.started.connect(worker.run)

      worker.sig_say.connect(self.say)
      worker.sig_log.connect(self.log)
      worker.sig_err.connect(self.error)

      if worker.connect():
        self.connected = True
        thread.start()
        self.thread = thread
        self.worker = worker
      else:
        self.log('Disconnected')

    @QtCore.pyqtSlot()
    def cleanup(self):
      if self.worker and not self.worker.event_close.is_set():
        self.worker.event_close.set()
        if self.thread.isRunning():
          self.thread.wait()

    def said(self,txt):
      self.chat('%s: %s' % (USER,txt))

    @QtCore.pyqtSlot(str)
    def say(self,txt):
      self.chat('%s: %s' % (SIBYL,txt),color='hotpink')

    @QtCore.pyqtSlot(str)
    def log(self,txt):
      self.chat('INFO: '+txt,color='darkgray',ts=False)

    @QtCore.pyqtSlot(str)
    def error(self,txt):
      self.connected = False
      self.chat(' *** '+txt,color='red',ts=False,strong=True)

    def chat(self,txt,color=None,ts=True,strong=False):

      color = (color or 'black')
      txt = self.html(txt).replace('\n','<br/>')
      if ts:
        txt = time.asctime()+' | '+txt
      txt = '<font color="%s">%s</font>' % (color,txt)
      if strong:
        txt = '<strong>%s</strong>' % txt
      self.chatpane.append(txt)

    def html(self,s):
      """escape characters that break html parsing"""

      s = s.replace('&','&amp;')
      chars = { '"':'&quot;', "'":'&#039;', '<':'&lt;', '>':'&gt;'}
      for (k,v) in chars.items():
        s = s.replace(k,v)
      return s

################################################################################
# Qt Connect Dialog class
################################################################################

if 'QtGui' in locals():
  class ConnectDialog(QtWidgets.QDialog):

    def __init__(self,parent):

      super(ConnectDialog,self).__init__(parent)
      self.initUI()

    def initUI(self):
      """create labels and edit boxes"""

      # create grid layout
      grid = QtWidgets.QGridLayout()
      grid.setSpacing(10)
      self.setLayout(grid)

      # add QLabels and QLineEdits
      grid.addWidget(QtWidgets.QLabel('Hostname',self),0,0)
      self.hostbox = QtWidgets.QLineEdit(self.parent().args.host,self)
      grid.addWidget(self.hostbox,0,1)

      grid.addWidget(QtWidgets.QLabel('Password',self),1,0)
      self.passbox = QtWidgets.QLineEdit(self.parent().pword,self)
      self.passbox.setEchoMode(QtWidgets.QLineEdit.Password)
      grid.addWidget(self.passbox,1,1)

      grid.addWidget(QtWidgets.QLabel('Use SSL',self),2,0)
      self.sslbox = QtWidgets.QCheckBox(self)
      self.sslbox.setChecked(self.parent().args.ssl)
      grid.addWidget(self.sslbox,2,1)

      grid.addWidget(QtWidgets.QLabel('Verify SSL',self),3,0)
      self.verifybox = QtWidgets.QCheckBox(self)
      self.verifybox.setChecked(not self.parent().args.noverify)
      grid.addWidget(self.verifybox,3,1)

      # add OK and Cancel buttons
      self.make_button(grid,'OK',4,0,self.accept)
      self.make_button(grid,'Cancel',4,1,self.reject)

      # disabled resizing and set name
      self.setFixedSize(self.sizeHint())
      self.setWindowTitle('Connect')

    def make_button(self,grid,name,x,y,func):
      """helper function to add a button to the grid"""

      button = QtWidgets.QPushButton(name,self)
      button.clicked.connect(func)
      button.resize(button.sizeHint())
      grid.addWidget(button,x,y)

    def get(self):
      return (self.hostbox.text(),self.passbox.text(),
          self.sslbox.isChecked(),not self.verifybox.isChecked())

################################################################################
# Main
################################################################################

if __name__ == '__main__':
  main()
