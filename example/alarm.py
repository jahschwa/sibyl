import datetime
from lib.protocol import Message
from lib.decorators import botinit,botconf,botcmd,botidle

@botinit
def init(bot):
  bot.add_var('alarms',[])

@botconf
def conf(bot):
  return {'name':'room_alarms','default':True,'parse':bot.conf.parse_bool}

@botcmd
def alarm(bot,mess,args):
  """set an alarm to go off later - alarm H:MM"""

  if mess.get_type()==Message.GROUP and not bot.opt('room_alarms'):
    return 'Alarms are disabled in chat rooms'

  try:
    (hr,mi) = args[0].split(':')
    now = datetime.datetime.now()
    target = now.replace(hour=int(hr),minute=int(mi),second=0,microsecond=0)
  except:
    return 'Time must be in the format H:MM'

  if target<now:
    target += datetime.timedelta(1)
  bot.alarms.append((mess,target))
  return 'Alarm added'

@botidle
def idle(bot):
  now = datetime.datetime.now()
  not_triggered = []
  for alarm in bot.alarms:
    if alarm[1]<=now:
      frm = alarm[0].get_from()
      name = frm.get_name()
      bot.protocol.send(name+': ALARM!',frm)
    else:
      not_triggered.append(alarm)
  bot.alarms = not_triggered
