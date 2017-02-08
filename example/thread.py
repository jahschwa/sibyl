#!/usr/bin/env python
#
# Very simple threading example where the "connection" is to stdin raw_input
# and logs to a file in the PWD called "thread.log"
#
# First the bot does protocol.connect(), which creates a new thread
# The bot sits in a loop, constantly calling chime() and protocol.process()
# the latter processes a single message and calls the bot's message callback
#
# At around every minute (xx:00) chime() will log "CHIME!"
#
# If you enter nothing at the prompt (just press enter) it is detected as a
# disconnect, the thread ends itself, and the protocol raises Disconnected
# then the bot catches the error and reconnects, then enters its loop again
#
# You can send as many message as you want, even if the bot is in the 5 sec long
# takes_forever() function, and you can send the disconnect message at any time
#
# Ctrl+C at any time will end the program
#
# You probably don't have to care about the Bot class that much. It's just a
# simplified SibylBot; the important stuff is in ThreadProtocol and BufferThread
#
# More details: https://github.com/TheSchwa/sibyl/wiki/Dev-threading

import logging,time,traceback
from threading import enumerate as enum
from threading import Thread
from Queue import Queue

DISCONNECT_STR = ''

################################################################################
# Custom Exception
################################################################################

class Disconnected(Exception):
  pass

################################################################################
# Main method
################################################################################

def main():
  bot = Bot()
  bot.run_forever()

################################################################################
# Bot Class
################################################################################

class Bot(object):

  def __init__(self):

    self.protocol = ThreadProtocol(self)
    self.next_chime = 0

    logging.basicConfig(filename='thread.log',filemode='w',level=logging.DEBUG,
        format='%(asctime).19s | %(name)-8.8s | %(levelname).3s | %(message)s')
    self.log = logging.getLogger('bot')

  def run_forever(self):

    self.log.info('starting')

    try:
      while True:
        self.serve()

    except KeyboardInterrupt:
      self.log.info('shutting down by KeyboardInterrupt')

    except BaseException as e:
      self.log.critical('Unhandled: %s' % e.__class__.__name__)
      self.log.debug(traceback.format_exc(e))

  def serve(self):

    try:

      if not self.protocol.is_connected():
        self.protocol.connect()

      self.protocol.process()
      self.chime()
      time.sleep(1)

    except Disconnected:
      self.log.error('disconnected')
      self.log.info('reconnecting in 5 sec')
      time.sleep(5)

  def _cb_message(self,msg):

    self.log.info('got msg: "%s"' % msg)
    self.log.info('Running takes_forever()')
    self.takes_forever()

  def takes_forever(self):

    time.sleep(5)
    self.log.info('Done running takes_forever()')

  def chime(self):

    t = time.time()
    if t<self.next_chime:
      return

    if self.next_chime:
      self.log.debug('CHIME!')
    self.next_chime = 60*int(t/60)+60

################################################################################
# ThreadProtocol Class
################################################################################

class ThreadProtocol(object):

  def __init__(self,bot):

    self.bot = bot
    self.log = logging.getLogger('protocol')
    self.connected = False

    self.thread = None
    self.queue = Queue()
    self.num = 0

  def is_connected(self):

    return self.connected

  def connect(self):

    self.num += 1
    self.thread = BufferThread(self)
    self.thread.start()

    self.connected = True
    self.log.info('connected with thread-%s' % self.num)
    self.log.info('all threads: %s' % [t.name for t in enum()])

  def process(self):

    if self.queue.empty():
      return

    self.log.info('%s messages waiting' % self.queue.qsize())
    msg = self.queue.get()

    if msg==DISCONNECT_STR:
      self.connected = False
      self.log.error('got disconnect msg')
      raise Disconnected

    self.bot._cb_message(msg)

################################################################################
# BufferThread Class
################################################################################

class BufferThread(Thread):

  def __init__(self,proto):

    super(BufferThread,self).__init__()
    self.daemon = True

    self.proto = proto
    self.log = logging.getLogger('thread-'+str(self.proto.num))

  def run(self):

    print ''

    while True:

      s = raw_input('[thread %s] enter text: ' % self.proto.num)
      self.log.info('got text: "%s"' % s)
      self.proto.queue.put(s)

      if s==DISCONNECT_STR:
        break

    self.log.info('thread closing')

################################################################################
# Allow running as script
################################################################################

if __name__=='__main__':
  main()
