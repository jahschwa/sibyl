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

import sys,os,unittest,logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from lib.config import Config
from lib.protocol import ConnectFailure,AuthFailure
import protocols

class Bot(object):

  def __init__(self):
    self.success = 0
    self.conf_file = 'temp.conf'
    self.conf = Config(self.conf_file)

  def called(self):
    return self.success==3

  def _cb_message(self):
    self.success += 1

  _cb_join_room_success = _cb_message
  _cb_join_room_failure = _cb_message

  def opt(self,name):
    return self.conf.opts[name]

class ProtocolTestCase(unittest.TestCase):

  def setUp(self):
    self.protocols = []
    for (p,d) in protocols.PROTOCOLS.items():
      self.protocols.append(d)

  def init_bot(self,config):
    bot = Bot()
    if config:
      config = config(bot)
      if not isinstance(config,list):
        config = [config]
      bot.conf.add_opts(config,'protocol')
    bot.conf.reload()
    return bot

  def init_protocol(self,p):
    log = logging.getLogger('protocol')
    log.addHandler(logging.NullHandler())
    return p['class'](self.init_bot(p['config']),log)

  def silent(self,func):
    so = sys.stdout
    with open(os.devnull,'wb') as f:
      sys.stdout = f
      try:
        x = func()
      finally:
        sys.stdout = so
    return x

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
      self.assertIsNone(caught,msg='['+p.__class__.__name__+'] '+str(caught))

  def test_is_connected(self):
    for p in self.protocols:
      p = self.init_protocol(p)
      caught = self.catch(p.connect,Exception)
      conn = self.silent(p.is_connected)
      self.assertFalse(conn,
          msg=('[%s] Reports connected before calling connect()'
          % p.__class__.__name__))

  def test_get_rooms(self):
    for p in self.protocols:
      p = self.init_protocol(p)
      rooms = len(self.silent(p.get_rooms))
      self.assertTrue(rooms==0,
          msg=('[%s] Reports being in rooms before calling join()'
          % p.__class__.__name__))
