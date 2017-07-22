#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2017 Joshua Haas <jahschwa.com>
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

import os,sys,imp,inspect

par = os.path.abspath(os.path.join(os.path.dirname(__file__),os.path.pardir))
sys.path.append(par)

from sibyl.lib.util import load_module
from sibyl.lib.protocol import Protocol

sys.path = sys.path[:-1]

ext = os.path.extsep
pwd = os.path.abspath(os.path.dirname(__file__))
ignore = ['__init__',os.path.basename(__file__).split(ext)[0],'skeleton']
files = [x for x in os.listdir(pwd) if x.startswith('sibyl_') and
    x.endswith(ext+'py') and x.split(ext)[0] not in ignore]

__all__ = ['PROTOCOLS','FAILED']
PROTOCOLS = {}
FAILED = []

for mod in files:

  fname = mod.split(ext)[0]
  protocol = fname.split('_')[1]

  try:
    mod = load_module(fname,pwd)
  except:
    FAILED.append(protocol)
    continue
  
  for (name,clas) in inspect.getmembers(mod,inspect.isclass):
    if issubclass(clas,Protocol) and clas!=Protocol:
      PROTOCOLS[fname] = {'class':clas,'config':None}
      __all__.append(name)
      exec('from %s import %s' % (fname,name))

  for (name,func) in inspect.getmembers(mod,inspect.isfunction):
    if getattr(func,'_sibylbot_dec_conf',False):
      PROTOCOLS[fname]['config'] = func
