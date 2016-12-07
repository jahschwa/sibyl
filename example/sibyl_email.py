import time,smtplib,imaplib,email
from email.mime.text import MIMEText
from threading import Thread
from Queue import Queue

from sibyl.lib.protocol import User,Room,Message,Protocol
from sibyl.lib.protocol import ProtocolError
from sibyl.lib.protocol import (PingTimeout,ConnectFailure,AuthFailure,
    ServerShutdown)

from sibyl.lib.decorators import botconf

################################################################################
# Config options
################################################################################

@botconf
def conf(bot):
  return [
    {'name':'address','req':True},
    {'name':'password','req':True},
    {'name':'delete','default':True,'parse':bot.conf.parse_bool},
    {'name':'imap'},
    {'name':'smtp'},
    {'name':'key','parse':bot.conf.parse_pass}
  ]

################################################################################
# User sub-class
################################################################################

class MailUser(User):

  def parse(self,user):
    self.user = user

  def get_name(self):
    return self.user

  def get_base(self):
    return self.user

  def __eq__(self,other):
    if not isinstance(other,MailUser):
      return False
    return self.user==other.user

  def __str__(self):
    return self.user

################################################################################
# Room class
################################################################################

class MailRoom(Room):

  def parse(self,name):
    self.name = name

  def get_name(self):
    return self.name

  def __eq__(self,other):
    if not isinstance(other,MailRoom):
      return False
    return self.name==other.name

################################################################################
# Protocol sub-class
################################################################################

class MailProtocol(Protocol):

  def setup(self):
    server = self.opt('email.address').split('@')[-1]
    self.imap_serv = (self.opt('email.imap') or ('imap.'+server))
    self.thread = IMAPThread(self)
    self.thread.start()
    self.smtp_serv = (self.opt('email.smtp') or ('smtp.'+server))
    self.smtp = None


  def connect(self):

    # we use IMAP to get new messages from the server
    # it runs in its own thread, appending messages asynchronously to a Queue
    self.log.debug('Attempting IMAP connection')
    self._connect_imap()
    self.log.info('IMAP successful')

    # we use SMTP to send emails
    self.log.debug('Attempting SMTP connection')
    self._connect_smtp()
    self.log.info('SMTP successful')

  def is_connected(self):
    return self.thread.imap is not None

  def disconnected(self):
    pass

  def process(self,wait=0):

    # every time SibylBot calls process(), this method synchronously checks for
    # new messages that the IMAPThread added while we were doing other things
    while not self.thread.msgs.empty():

      # check if there was a problem connecting and raise it syncronously
      mail = self.thread.msgs.get()
      if isinstance(mail,Exception):
        raise mail

      # begin parsing the e-mail
      frm = email.utils.parseaddr(mail['From'])[1]
      user = MailUser(self,frm)
      body = mail.get_payload().replace('\r','').strip()

      # check for authentication key if configured
      if self.opt('email.key') and self.opt('email.key').get() not in body:
        self.log.warning('Invalid key from "%s"; dropping message' % user)
        self.send('Invalid or missing key; commands forbidden',user)
        continue

      # finish parsing the e-mail and send it
      body = body.split('\n')[0].strip()
      msg = Message(user,body)
      ellip = ('...' if len(body)>20 else '')
      self.log.debug('Mail from "%s" with body "%.20s%s"' % (user,body,ellip))

      # pass the message on to the bot for command execution
      self.bot._cb_message(msg)

  def shutdown(self):
    pass

  # REF: http://stackoverflow.com/a/14678470
  def send(self,text,to):

    # SMTP connections are short-lived, so we might need to reconnect
    try:
      status = self.smtp.noop()[0]
    except:
      status = -1
    if status!=250:
      self._connect_smtp()

    msg = MIMEText(text)
    msg['Subject'] = 'Sibyl reply'
    msg['From'] = self.opt('email.address')
    msg['To'] = str(to)

    self.smtp.sendmail(msg['From'],msg['To'],msg.as_string())

  def broadcast(self,text,room,frm=None):
    pass

  def join_room(self,room):
    bot._cb_join_room_failure(room,'Not supported')

  def part_room(self,room):
    pass

  def _get_rooms(self,flag):
    return []

  def get_occupants(self,room):
    return []

  def get_nick(self,room):
    return None

  def get_real(self,room,nick):
    return nick

  def get_user(self):
    return MailUser(self,self.opt('email.address'),Message.PRIVATE)

  def new_user(self,user,typ=None,real=None):
    return MailUser(self,user,typ,real)

  def new_room(self,name,nick=None,pword=None):
    return MailRoom(self,name,nick,pword)

################################################################################
# Helper functions
################################################################################

  # convenience function for connecting the IMAP thread
  def _connect_imap(self):
    self.thread.connect()

  # convenience function for connecting to the SMTP server
  def _connect_smtp(self):

    # all major email providers support SSL, so use it
    try:
      self.smtp = smtplib.SMTP(self.smtp_serv,port=587)
      self.smtp.starttls()
      self.smtp.ehlo()
    except:
      raise ConnectFailure

    # if the protocol raises AuthFailure, SibylBot will never try to reconnect
    try:
      self.smtp.login(self.opt('email.address'),self.opt('email.password'))
    except:
      raise AuthFailure

################################################################################
# IMAPThread class
################################################################################

class IMAPThread(Thread):

  def __init__(self,proto):

    super(IMAPThread,self).__init__()
    self.daemon = True

    self.proto = proto
    self.imap = None
    self.msgs = Queue()

  # this method is called when doing IMAPThread().start()
  # we will be using IMAP IDLE push notifications as described at:
  #   https://tools.ietf.org/html/rfc2177
  # which allows us to near-instantly respond to new messages without polling
  # REF: http://stackoverflow.com/a/18103279
  def run(self):

    while True:

      # reconnect logic is handled in SibylBot, until that happens do nothing
      if not self.imap:
        time.sleep(1)
        continue

      # wait for the server to send us a new notification (this command blocks)
      line = self.imap.readline().strip()

      # if the line is blank, the server closed the connection
      if not line:
        try:
          self.connect()

        # raising exceptions in a Thread is messy, so we'll queue it instead
        except ProtocolError as e:
          self.imap = None
          self.msgs.put(e)

      # if the line ends with "EXISTS" then there is a new message waiting
      elif line.endswith('EXISTS'):

        # to end the IDLE state and actually get the message we issue "DONE"
        self.cmd('DONE')

        # after we get the new message(s) and Queue them, we enter IDLE again
        self.get_mail()
        self.cmd('IDLE')

  def connect(self):

    try:
      self.imap = imaplib.IMAP4_SSL(self.proto.imap_serv)
    except:
      raise ConnectFailure

    try:
      self.imap.login(self.proto.opt('email.address'),
        self.proto.opt('email.password'))
    except:
      raise AuthFailure

    # we have to specify which Inbox to use, and then enter the IDLE state
    self.imap.select()
    self.cmd('IDLE')

  # @param s (str) the SMTP command to send
  def cmd(self,s):
    self.imap.send("%s %s\r\n"%(self.imap._new_tag(),s))

  def get_mail(self):

    # only look at messages that don't have the "\\SEEN" flag
    (status,nums) = self.imap.search('utf8','UNSEEN')

    # get new messages and add them to our Queue
    for n in nums:
      msg = self.imap.fetch(n,'(RFC822)')[1][0][1]
      self.msgs.put(email.message_from_string(msg))

      # flag messages for deletion if configured to do so
      if self.proto.opt('email.delete'):
        self.imap.store(n,'+FLAGS','\\Deleted')

    # this tells the server to actually delete all flagged messages
    self.imap.expunge()
