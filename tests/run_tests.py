#!/usr/bin/env python2
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

from lib.util import load_module

def main():

  suite = get_suite()
  unittest.TextTestRunner().run(suite)

def get_suite():

  suite = unittest.TestSuite()

  pwd = os.path.abspath(os.path.join(os.path.dirname(__file__),'.'))
  mods = [mod.split('.')[0] for mod in os.listdir(pwd)
      if mod.endswith('.py') and mod.startswith('test')]

  mods = ['test_protocol']

  for mod in mods:
    mod = load_module(mod,pwd)
    try:
      suite.addTest(mod.suite())
    except:
      suite.addTest(unittest.TestLoader().loadTestsFromModule(mod))

  return suite

if __name__=='__main__':
  main()
