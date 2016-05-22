#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2016 Joshua Haas <jahschwa.com>
#
# This file is part of Sibyl.
#
# Sibyl is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
################################################################################

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
