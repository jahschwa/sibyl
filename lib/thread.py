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

import threading,traceback

class SmartThread(threading.Thread):
  """smart threads log exceptions"""

  def __init__(self,bot,func,mess,args):

    super(SmartThread,self).__init__()
    self.daemon = True

    self.bot = bot
    self.func = func
    self.mess = mess
    self.args = args

  def run(self):

    reply = None
    try:
      reply = self.func(self.bot,self.mess,self.args)
    except Exception as e:
      fname = self.func._sibylbot_dec_chat_name
      self.bot._log_ex(e,
          'Error while executing threaded cmd "%s":' % fname,
          '  Message text: "%s"' % self.mess.get_text())
      reply = self.bot.MSG_ERROR_OCCURRED
      if self.bot.opt('except_reply'):
        reply = traceback.format_exc(e).split('\n')[-2]

    if reply:
      self.bot.send(reply,self.mess.get_from())
