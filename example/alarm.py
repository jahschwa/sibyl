import datetime
from sibyl.lib.protocol import Message
from sibyl.lib.decorators import botinit,botconf,botcmd,botidle

@botinit
def init(bot):
  bot.add_var('alarms',[])

@botconf
def conf(bot):
  return {'name':    'allow_rooms',
          'default': True,
          'parse':   bot.conf.parse_bool}

@botcmd
def alarm(bot,mess,args):
  """set an alarm to go off later - alarm H:MM"""

  # disable the command in rooms based on alarm.allow_rooms
  if mess.get_type()==Message.GROUP and not bot.opt('alarm.allow_rooms'):
    return 'Alarms are disabled in chat rooms'

  # try to parse the user-specified time
  try:
    (hr,mi) = args[0].split(':')
    now = datetime.datetime.now()
    target = now.replace(hour=int(hr),minute=int(mi),second=0,microsecond=0)
  except ValueError:
    return 'Time must be in the format H:MM'

  # account for alarms that should be tomorrow
  if target<now:
    target += datetime.timedelta(1)

  # store the alarm
  bot.alarms.append((mess,target))
  return 'Alarm added'

@botidle
def idle(bot):

  now = datetime.datetime.now()
  not_triggered = []

  # iterate over all our stored alarms and trigger those that have passed
  for (mess,target) in bot.alarms:
    if target<=now:
      name = mess.get_user().get_name()
      frm = mess.get_from()
      bot.send(name+': ALARM!',frm)
    else:
      not_triggered.append((mess,target))

  # update our stored alarms to remove those that just triggered
  bot.alarms = not_triggered
