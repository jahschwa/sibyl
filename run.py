#!/usr/bin/env python

import sys,os,argparse

from sibyl.sibylbot import SibylBot

parser = argparse.ArgumentParser()
parser.add_argument('-c',default='sibyl.conf',help='path to config file',metavar='file')
parser.add_argument('-d',action='store_true',help='run as daemon')
args = parser.parse_args()

bot = SibylBot(args.c)

if args.d:
  with open('/var/run/sibyl/sibyl.pid','w') as f:
    f.write(str(os.getpid()))

bot.run_forever()
