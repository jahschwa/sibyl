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

import sys,os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from lib.protocol import User,Message

class MockUser(User):

  def parse(self,user,typ):
    self.user = user
    self.typ = typ

  def get_name(self):
    return 'NAME:'+self.user

  def get_room(self):
    if self.typ==Message.PRIVATE:
      return None
    return 'MOCK_ROOM'

  def get_base(self):
    return 'BASE:'+self.user

  def __eq__(self,other):
    if not isinstance(other,MockUser):
      return False
    return str(self)==str(other)

  def __str__(self):
    user = 'STR:'+self.user
    if self.get_room():
      user += ':ROOM'
    return user

