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

from lib.protocol import Message

class MessageTypesTestCase(unittest.TestCase):

  def test_message_types(self):
    self.check(Message.TYPES)

  def test_message_statuses(self):
    self.check(Message.STATUSES)

  def check(self,types):
    length = len(types)
    for typ in types:
      self.assertTrue(hasattr(Message,typ),msg=('Missing %s'%typ))
      value = getattr(Message,typ)
      msg = '%s=%s not in [%s,%s]' % (typ,value,0,length-1)
      self.assertIn(value,range(0,length),msg=msg)
