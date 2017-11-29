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

import sys,os,logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from lib.sibylbot import SibylBot
from lib.config import Config
from mock_protocol import MockProtocol
from mock_log import MockLog

class Bot(SibylBot):

  def __init__(self,log=False):

    self.result = []

    self.opts = Config('test.conf').get_default()

    self.opts['chat_proto'] = ['MOCK']
    self.opts['username'] = 'BOT:USERNAME'
    self.opts['password'] = 'BOT:PASSWORD'
    self.opts['nick_name'] = 'BOT:NICK'
    self.opts['cmd_prefix'] = 'BOT:PREFIX'
    self.opts['rooms'] = [{'room':'MOCK_ROOM','nick':None,'pass':None}]
    self.opts['only_direct'] = False
    self.opts['recon_wait'] = 0

    self._SibylBot__finished = False
    self._SibylBot__reboot = False
    self.last_cmd = {}
    self.plugins = ['sibylbot']
    self.hooks = {x:{} for x in ['chat','init','down','con','discon','recon',
        'rooms','roomf','msg','priv','group','status','err','idle']}

    self.hooks['chat']['MOCK'] = lambda m,a: 'HOOK_CHAT'
    self.hooks['init']['MOCK'] = lambda : 'HOOK_INIT'
    self.hooks['down']['MOCK'] = lambda : 'HOOK_DOWN'
    self.hooks['con']['MOCK'] = lambda : 'HOOK_CON'
    self.hooks['discon']['MOCK'] = lambda e: 'HOOK_DISCON'
    self.hooks['recon']['MOCK'] = lambda : 'HOOK_RECON'
    self.hooks['rooms']['MOCK'] = lambda r: 'HOOK_ROOMS'
    self.hooks['roomf']['MOCK'] = lambda r,e: 'HOOK_ROOMF'
    self.hooks['msg']['MOCK'] = lambda m,c: 'HOOK_MSG'
    self.hooks['priv']['MOCK'] = lambda m,c: 'HOOK_PRIV'
    self.hooks['group']['MOCK'] = lambda m,c: 'HOOK_GROUP'
    self.hooks['status']['MOCK'] = lambda m: 'HOOK_STATUS'
    self.hooks['idle']['MOCK'] = lambda : 'HOOK_IDLE'

    if log:
      logging.basicConfig(filename='test.log',
        format='%(asctime).19s | %(name)-8.8s | %(levelname).3s | %(message)s',
        level=logging.DEBUG)
      self.log = logging.getLogger('bot')
      self.protocol = MockProtocol(self,logging.getLogger('protocol'))
    else:
      self.log = MockLog()
      self.protocol = MockProtocol(self,self.log)

    self._SibylBot__run_hooks('init')

  def opt(self,name):
    return self.opts[name]

  def _cb_message(self,mess):
    self.result.append('CB_MSG')
    result = super(Bot,self)._cb_message(mess)
    if result:
      self.result.append(result)

  def _cb_join_room_success(self,room):
    self.result.append('CB_ROOM_S')
    super(Bot,self)._cb_join_room_success(room)

  def _cb_join_room_failure(self,room,error):
    self.result.append('CB_ROOM_F')
    super(Bot,self)._cb_join_room_failure(room,error)

  def get_result(self):
    result = self.result
    self.result = []
    return result

  def _SibylBot__run_hooks(self,hook,*args):

    self.log.debug('run_hooks(%s)' % hook)
    for (name,func) in self.hooks[hook].items():
      self.result.append(func(*args))

  def serve_once(self):

    self.protocol.connect()
    self.protocol.process()
