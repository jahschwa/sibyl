import sys

sys.path.append('/media/Data/git/sibyl')

from protocol import Message
from protocols.sibyl_xmpp import JID,XMPP

class Log(object):
  def debug(self,text):
    print 'DEB: '+text
  def info(self,text):
    print 'INF: '+text
  def warn(self,text):
    print 'WAR: '+text
  def error(self,text):
    print 'ERR: '+text
  def critical(self,text):
    print 'CRI: '+text

class Bot(object):

  log = Log()

  username = 'debug@jahschwa.com'
  password = 'bedbug'
  resource = 'dev'
  server = None
  port = 5222
  ping_freq = 0
  ping_timeout = 3
  recon_wait = 60
  xmpp_debug = False
  priv_domain = True
  
  def callback(self,mess):
    print 'CAL: '+str(mess)

  def join_room_success(self,room):
    print 'MUC: success joining room "%s"' % room

  def join_room_failure(self,room,error):
    print 'MUC: failed to join room "%s" (%s)' % (room,error)



bot = Bot()
x = XMPP(bot)
x.connect(bot.username,bot.password)
x.join_room('debug@conference.jahschwa.com','sibyldev','bedbug')
while True:
  x.process()
