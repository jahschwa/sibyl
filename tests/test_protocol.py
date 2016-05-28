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

import sys,os,unittest,logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from lib.config import Config
from lib.protocol import ConnectFailure,AuthFailure
import protocols

class Bot(object):

  def __init__(self):
    self.success = 0
    self.username = '127.0.0.1'
    self.password = ''
    self.conf_file = 'temp.conf'
    self.conf = Config(self.conf_file)

  def called(self):
    return self.success==3

  def _cb_message(self):
    self.success += 1

  _cb_join_room_success = _cb_message
  _cb_join_room_failure = _cb_message

class ProtocolTestCase(unittest.TestCase):

  def setUp(self):
    self.protocols = []
    for (p,d) in protocols.PROTOCOLS.items():
      self.protocols.append(d)

  def init_bot(self,config):
    bot = Bot()
    if config:
      for opt in config(bot):
        setattr(bot,opt['name'],opt['default'])
    return bot

  def init_protocol(self,p):
    return p['class'](self.init_bot(p['config']),logging.getLogger())

  def silent(self,func):
    so = sys.stdout
    with open(os.devnull,'wb') as f:
      sys.stdout = f
      func()
    sys.stdout = so

  def catch(self,func,ex):
    try:
      self.silent(func)
    except ex:
      return None
    except Exception as e:
      return 'Expected %s but got %s' % (ex.__name__,e.__class__.__name__)
    return 'Expected %s but nothing raised' % ex.__class__.__name__

  def test_connect_fail(self):
    for p in self.protocols:
      p = self.init_protocol(p)
      caught = self.catch(p.connect,ConnectFailure)
      self.assertIsNone(caught,msg=caught)

  def test_is_connected(self):
    for p in self.protocols:
      p = self.init_protocol(p)
      caught = self.catch(p.connect,Exception)
      self.assertFalse(p.is_connected())

  def test_get_rooms(self):
    for p in self.protocols:
      p = self.init_protocol(p)
      self.assertTrue(len(p.get_rooms())==0)
