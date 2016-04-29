import sys

from sibyl.sibylbot import SibylBot

conf = 'sibyl.conf'
if len(sys.argv)>1:
  conf = sys.argv[1]

bot = SibylBot(conf)
bot.run_forever()
