#!/usr/bin/env python

import sys,os,argparse

from sibylbot import SibylBot

# append the current directory so cmds can import files correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'.')))

parser = argparse.ArgumentParser()
parser.add_argument('-c',default='sibyl.conf',help='path to config file',metavar='file')
parser.add_argument('-d',action='store_true',help='run as daemon')
args = parser.parse_args()

bot = SibylBot(args.c)

# if we're running as a daemon we need to put our PID in the pidfile
if args.d:
  with open('/var/run/sibyl/sibyl.pid','w') as f:
    f.write(str(os.getpid()))

bot.run_forever()
