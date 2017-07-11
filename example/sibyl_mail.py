import imaplib,smtplib,email,time
from email.mime.text import MIMEText
from threading import Thread
from Queue import Queue

from sibyl.lib.protocol import User,Room,Protocol,Message
from sibyl.lib.decorators import botconf

################################################################################
# Exceptions Boilerplate
################################################################################

from sibyl.lib.protocol import ProtocolError as SuperProtocolError
from sibyl.lib.protocol import PingTimeout as SuperPingTimeout
from sibyl.lib.protocol import ConnectFailure as SuperConnectFailure
from sibyl.lib.protocol import AuthFailure as SuperAuthFailure
from sibyl.lib.protocol import ServerShutdown as SuperServerShutdown

class ProtocolError(SuperProtocolError):
  def __init__(self):
    self.protocol = __name__.split('_')[-1]

class PingTimeout(SuperPingTimeout,ProtocolError):
  pass

class ConnectFailure(SuperConnectFailure,ProtocolError):
  pass

class AuthFailure(SuperAuthFailure,ProtocolError):
  pass

class ServerShutdown(SuperServerShutdown,ProtocolError):
  pass

################################################################################
# Config Options
################################################################################

@botconf
def conf(bot):
  return [
    {'name':'address','req':True},
    {'name':'password','req':True},
    {'name':'imap'},
    {'name':'smtp'},
  ]

################################################################################
# MailUser
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
# MailRoom
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
# IMAPThread
################################################################################

class IMAPThread(Thread):

  def __init__(self,proto):

    super(IMAPThread,self).__init__()
    self.daemon = True

    self.proto = proto
    self.imap = None
    self.msgs = Queue()

  def cmd(self,s):

    self.imap.send("%s %s\r\n"%(self.imap._new_tag(),s))

  def connect(self):

    try:
      self.imap = imaplib.IMAP4_SSL(self.proto.imap_serv)
    except:
      raise ConnectFailure

    try:
      self.imap.login(self.proto.opt('mail.address'),
          self.proto.opt('mail.password'))
    except:
      raise AuthFailure

    self.imap.select()
    self.cmd('IDLE')

  def run(self):

    while True:

      if not self.imap:

        time.sleep(1)
        continue

      line = self.imap.readline().strip()

      if not line:

        try:
          self.connect()
        except ProtocolError as e:
          self.msgs.put(e)
          self.imap = None

      elif line.endswith('EXISTS'):

        self.cmd('DONE')
        (status,nums) = self.imap.search('utf8','UNSEEN')
        for n in nums[0].split(' '):
          msg = self.imap.fetch(n,'(RFC822)')[1][0][1]
          self.msgs.put(email.message_from_string(msg))
        self.cmd('IDLE')

################################################################################
# MailProtocol
################################################################################

class MailProtocol(Protocol):

  def setup(self):

    server = self.opt('mail.address').split('@')[-1]
    self.smtp_serv = (self.opt('mail.smtp') or ('smtp.'+server))
    self.imap_serv = (self.opt('mail.imap') or ('imap.'+server))

    self.smtp = None

    self.thread = IMAPThread(self)
    self.thread.start()

  def connect(self):

    self.log.debug('Attempting IMAP connection')
    self.thread.connect()
    self.log.info('IMAP successful')

    self.log.debug('Attempting SMTP connection')
    self._connect_smtp()
    self.log.info('SMTP successful')

  def _connect_smtp(self):

    try:
      self.smtp = smtplib.SMTP(self.smtp_serv,port=587)
      self.smtp.starttls()
      self.smtp.ehlo()
    except:
      raise ConnectFailure

    try:
      self.smtp.login(self.opt('mail.address'),self.opt('mail.password'))
    except:
      raise AuthFailure

  def is_connected(self):

    return self.thread.imap is not None

  def shutdown(self):

    pass

  def process(self):

    while not self.thread.msgs.empty():

      mail = self.thread.msgs.get()
      if isinstance(mail,Exception):
        raise mail

      frm = email.utils.parseaddr(mail['From'])[1]
      user = MailUser(self,frm)
      body = mail.get_payload().split('\n')[0].strip()
      msg = Message(user,body)
      self.log.debug('Got mail from "%s"' % frm)
      self.bot._cb_message(msg)

  def send(self,text,to):

    try:
      status = self.smtp.noop()[0]
    except:
      status = -1
    if status!=250:
      self._connect_smtp()

    msg = MIMEText(text)
    msg['Subject'] = 'Sibyl reply'
    msg['From'] = self.opt('mail.address')
    msg['To'] = str(to)
    self.smtp.sendmail(msg['From'],msg['To'],msg.as_string())

  def broadcast(self,text,room,frm=None,users=None):
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
    return ''

  def get_real(self,room,nick):
    return nick

  def get_user(self):
    return MailUser(self,self.opt('mail.address'))

  def new_user(self,user,typ=None,real=None):
    return MailUser(self,user,typ,real)

  def new_room(self,name,nick=None,pword=None):
    return MailRoom(self,name,nick,pword)
