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

import sys,os,unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from lib.protocol import Message,ConnectFailure
from mock_bot import Bot
from mock_protocol import QueueEmpty
from mock_user import MockUser

class HooksTestCase(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    if os.path.isfile('test.log'):
      os.remove('test.log')

  def setUp(self):
    with open('test.log','a') as f:
      f.write('\n'+'='*80+'\n'+self._testMethodName+'\n'+'='*80+'\n\n')
    self.bot = Bot(log=True)
    self.hooks = {x:{} for x in ['chat','init','down','con','discon','recon',
        'rooms','roomf','msg','priv','group','status','idle']}

  def process(self,hooks,cond=True):
    try:
      self.bot.run_forever()
    except QueueEmpty:
      pass
    if not isinstance(hooks,list):
      hooks = [hooks]
    result = self.bot.get_result()
    self.bot.log.debug('RESULT: %s' % result)
    if cond:
      for hook in hooks:
        self.assertIn(hook,result)
    else:
      for hook in hooks:
        self.assertNotIn(hook,result)

  def process_chat(self,text,typ,direct=False,prefix=None,cond=True):
    self.bot.opts['only_direct'] = direct
    self.bot.opts['cmd_prefix'] = prefix
    user = MockUser('MOCK_USERNAME',typ)
    msg = Message(typ,user,text)
    self.bot.protocol.queue_msg(msg)
    try:
      self.bot.run_forever()
    except QueueEmpty:
      pass
    if cond:
      self.assertIn(user.get_base(),self.bot.last_cmd)
    else:
      self.assertNotIn(user.get_base(),self.bot.last_cmd)

  def test_chat_hook_runs_private(self):
    self.process_chat('MOCK',Message.PRIVATE)

  def test_chat_hook_fails_private(self):
    self.process_chat('',Message.PRIVATE,cond=False)

  def test_chat_hook_runs_group_notonlydirect_nocmdprefix(self):
    self.process_chat('MOCK',Message.GROUP)

  def test_chat_hook_fails_group_notonlydirect_nocmdprefix(self):
    self.process_chat('',Message.GROUP,cond=False)

  def test_chat_hook_runs_group_onlydirect_nocmdprefix(self):
    self.process_chat('MOCK_NICKNAME MOCK',Message.GROUP,direct=True)

  def test_chat_hook_fails_group_onlydirect_nocmdprefix(self):
    self.process_chat('MOCK',Message.GROUP,direct=True,cond=False)

  def test_chat_hook_runs_group_notonlydirect_cmdprefix(self):
    self.process_chat('!MOCK',Message.GROUP,prefix='!')

  def test_chat_hook_fails_group_notonlydirect_cmdprefix(self):
    self.process_chat('MOCK',Message.GROUP,prefix='!',cond=False)

  def test_chat_hook_runs_group_onlydirect_cmdprefix(self):
    self.process_chat('MOCK_NICKNAME MOCK',Message.GROUP,True,'!')
    self.process_chat('!MOCK',Message.GROUP,True,'!')

  def test_chat_hook_fails_group_onlydirect_cmdprefix(self):
    self.process_chat('MOCK',Message.GROUP,direct=True,prefix='!',cond=False)

  def test_init_hook_runs(self):
    self.assertIn('HOOK_INIT',self.bot.get_result())

  def test_down_hook_runs(self):
    self.process('HOOK_DOWN')

  def test_con_hook_runs(self):
    self.process('HOOK_CON')

  def test_discon_hook_runs(self):
    self.bot.protocol.queue_msg(ConnectFailure)
    self.process('HOOK_DISCON')

  def test_recon_hook_runs(self):
    self.bot.protocol.queue_msg(ConnectFailure)
    self.process('HOOK_RECON')

  def test_rooms_hook_runs(self):
    self.process('HOOK_ROOMS')

  def test_rooms_hook_fails(self):
    self.bot.protocol.connect()
    self.bot.protocol.join_room('','',success=False)
    self.assertNotIn('HOOK_ROOMS',self.bot.get_result())

  def test_roomf_hook_runs(self):
    self.bot.protocol.connect()
    self.bot.protocol.join_room('','',success=False)
    self.assertIn('HOOK_ROOMF',self.bot.get_result())

  def test_roomf_hook_fails(self):
    self.bot.protocol.connect()
    self.bot.protocol.join_room('','')
    self.assertNotIn('HOOK_ROOMF',self.bot.get_result())

  def test_msg_hook_runs_private(self):
    self.bot.protocol.queue_msg()
    self.process('HOOK_MSG')

  def test_msg_hook_runs_group(self):
    user = MockUser('MOCK_USERNAME',Message.GROUP)
    msg = Message(Message.GROUP,user,'MOCK')
    self.bot.protocol.queue_msg(msg)
    self.process('HOOK_MSG')

  def test_priv_hook_runs(self):
    user = MockUser('MOCK_USERNAME',Message.PRIVATE)
    msg = Message(Message.PRIVATE,user,'MOCK')
    self.bot.protocol.queue_msg(msg)
    self.process('HOOK_PRIV')

  def test_group_hook_runs(self):
    user = MockUser('MOCK_USERNAME',Message.GROUP)
    msg = Message(Message.GROUP,user,'MOCK')
    self.bot.protocol.queue_msg(msg)
    self.process('HOOK_GROUP')

  def test_status_hook_runs(self):
    user = MockUser('MOCK_USERNAME',Message.PRIVATE)
    msg = Message(Message.STATUS,user,'MOCK',Message.AVAILABLE,'MOCK_STATUS')
    self.bot.protocol.queue_msg(msg)
    self.process('HOOK_STATUS')

  def test_hooks_fail_status(self):
    types = [Message.STATUS,Message.PRIVATE,Message.GROUP,Message.ERROR]
    users = [Message.PRIVATE,Message.PRIVATE,Message.GROUP,Message.PRIVATE]
    hooks = ['HOOK_STATUS','HOOK_PRIVATE','HOOK_GROUP','HOOK_ERROR']
    statuses = [Message.AVAILABLE,None,None,None]
    msgs = ['MOCK_STATUS',None,None,None]

    for (typ,user,hook,status,msg) in zip(types,users,hooks,statuses,msgs):
      user = MockUser('MOCK_USERNAME',user)
      msg = Message(typ,user,'MOCK',status,msg)
      self.bot.protocol.queue_msg(msg)
      self.process([x for x in hooks if x!=hook],False)

  def test_idle_hook_runs(self):
    self.process('HOOK_IDLE')

if __name__=='__main__':
  unittest.main()
