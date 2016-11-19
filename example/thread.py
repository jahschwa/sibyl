#!/usr/bin/env python
#
# Very simple threading example where the "connection" is to stdin raw_input
# and logs to a file in the PWD called "thread.log"
#
# First the bot does protocol.connect(), which creates a new thread
# The bot sits in a loop, constantly calling idle_proc() and protocol.process()
# the latter blocks for max 1 second, processes a single message, and calls
# the bot's message callback
#
# At around every minute (xx:00) the idle_proc() will log "MINUTE!"
#
# If you enter nothing at the prompt (just press enter) it is detected as a
# disconnect, the thread ends itself, and the protocol raises Disconnected
# then the bot catches the error and reconnects, then enters its loop again
#
# You can send as many message as you want, even if the bot is in the 5 sec long
# "takes_forever" function, and you can send the disconnect message at any time
#
# Ctrl+C at any time will end the program
#
# You probably don't have to care about the Bot class that much. It's basically
# just a trimmed-down SibylBot.
#
# The important stuff is in ThreadProtocol and BufferThread

import logging,time,traceback
from threading import enumerate as enum
from threading import Thread,Event
from Queue import Queue

DISCONNECT_STR = ''

def main():

  # create a bot and run forever
  bot = Bot()
  bot.run_forever()

class Disconnected(Exception):
  pass

class Bot(object):

  def __init__(self):
    """initialise protocol, logging, and alarm"""

    self.protocol = ThreadProtocol(self)
    logging.basicConfig(filename='thread.log',filemode='w',level=logging.DEBUG,
        format='%(asctime).19s | %(name)-8.8s | %(levelname).3s | %(message)s')
    self.log = logging.getLogger('bot')
    self.alarm = 0

  def _cb_message(self,msg):
    """log messages and run a 5-second hook"""

    self.log.info('got mess: "%s"' % msg)
    self.log.info('Running hook takes_forever')
    self.takes_forever()

  def takes_forever(self):
    """take 5 seconds doing nothing to demonstrate threadiness"""

    time.sleep(5)
    self.log.info('Done running takes_forever')

  def run_forever(self):
    """connect, run idle_proc, process messages, catch exceptions"""

    self.log.info('bot starting')
    # outer try loop catches all exceptions, and this while loop runs forever
    try:
      while True:

        # inner try loop catches Disconnected
        try:

          # try to connect if needed and make sure we're successful
          if not self.protocol.is_connected():
            self.protocol.connect()
            if not self.protocol.is_connected():
              raise Disconnected

          # main loop processing
          self.idle_proc()
          self.protocol.process()

        # reconnect after 5 seconds
        except Disconnected:
          self.log.error('disconnected')
          self.log.info('reconnecting in 5 sec')
          time.sleep(5)

    except KeyboardInterrupt:
      self.log.info('shutting down by KeyboardInterrupt')

    # print traceback info for debugging
    except BaseException as e:
      self.log.critical(e.__class__.__name__)
      print traceback.format_exc(e)

  def idle_proc(self):
    """log 'MINUTE!' at approx. :00"""

    t = time.time()
    if t<self.alarm:
      return

    if self.alarm:
      self.log.debug('MINUTE!')
    self.alarm = t+(60-int(t)%60)

class ThreadProtocol(object):

  def __init__(self,bot):
    """create a queue and events"""

    self.bot = bot
    self.log = logging.getLogger('protocol')
    self.thread = None
    self.connected = False
    self.num = 0

  def is_connected(self):
    """return True if connected"""

    return self.connected

  def connect(self):
    """create a new thread to receive data"""

    # make sure we have unique variables for each new thread, and don't forget
    # queue elements if we disconnected
    q = Queue()
    if hasattr(self,'queue'):
      for x in self.queue.queue:
        if x!=DISCONNECT_STR:
          q.put(x)
    self.queue = q
    self.event_data = Event()
    if not self.queue.empty():
      self.event_data.set()
    self.event_close = Event()

    # create a new thread and start it
    self.num += 1
    self.thread = BufferThread(self.queue,
        self.event_data,self.event_close,self.num)
    self.thread.start()
    self.connected = True
    self.log.info('connected with thread-%s' % self.num)
    self.log.info('all threads: %s' % [t.name for t in enum()])

  def process(self):
    """process a single message from the queue and return"""

    # if the thread is dead raise disconnected
    if not self.thread.is_alive():
      self.connected = False
      self.log.error('thread is dead')
      raise Disconnected

    # wait for a new message for a max of 1 second
    # we could get almost the same result by just checking if the queue is
    # empty, but waiting for max of 1 second is nice for @botidle hooks
    if not self.event_data.wait(1):
      return

    # pass the next message to the bot, or disconnect on DISCONNECT_STR
    self.log.info('%s messages waiting' % self.queue.qsize())
    msg = self.queue.get()

    # this check is necessary if the thread dies while we're in the wait() loop
    if msg==DISCONNECT_STR:
      self.connected = False

      # in this protocol, setting self.event_close() is pointless, but we should
      # do it anyway to make it as likely as possible the thread will stop
      self.event_close.set()
      self.log.error('got disconnect msg')
      raise Disconnected

    self.bot._cb_message(msg)

    # if we got the last message, clear the event_data Event
    if self.queue.empty():
      self.event_data.clear()

class BufferThread(Thread):

  def __init__(self,q,d,c,i):
    """create a new thread that reads from stdin and appends to a Queue"""

    # daemons die when their parent dies apparently?
    super(BufferThread,self).__init__()
    self.daemon = True

    self.queue = q
    self.event_data = d
    self.event_close = c
    self.num = i
    self.log = logging.getLogger('thread-'+str(self.num))

  def run(self):
    """read from stdin, add to the queue, set the event_data Event"""

    print ''

    # the thread ends itself upon receiving a blank message, but can also be
    # ended when self.event_close is set (not relevant here because raw_input
    # blocks forever, but could be relevant in an actual protocol)
    try:
      while not self.event_close.is_set():

        # upon receiving data, add it to the queue and set self.event_data
        s = raw_input('[thread %s] enter data: ' % self.num)
        self.log.info('got data: "%s"' % s)
        self.queue.put(s)
        self.event_data.set()
        if s==DISCONNECT_STR:
          break
    except:
      pass
    self.log.info('thread closing')

if __name__=='__main__':
  main()
