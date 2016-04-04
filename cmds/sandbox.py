#!/usr/bin/env python

from sibyl.jabberbot import botcmd
from sibyl.sibylbot import botconf

@botconf
def add_config(bot):

  return [{'name' : 'myopt',
           'default' : 0}]

@botcmd
def check(bot,mess,args):

  bot.send_simple_reply(mess,str(bot.myopt))
