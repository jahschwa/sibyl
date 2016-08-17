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

import logging

from lib.util import get_caller

class Log(object):
  """abstraction to name the logging module based on the calling function"""

  def __get_logger(self):
    """go back in the stack to find the file that called me"""

    return logging.getLogger(get_caller(lvl=4))

  def __log(self,lvl,msg):
    """log a message by getting a logger for the caller's filename"""

    self.__get_logger().log(lvl,msg)

################################################################################
# the rest of the functions in this class emulate functionality from logging   #
################################################################################

  def log(lvl,msg):

    levels = {'debug':logging.DEBUG,
              'info':logging.INFO,
              'warning':logging.WARNING,
              'error':logging.ERROR,
              'critical':logging.CRITICAL}
    self.__log(levels[lvl],msg)

  def debug(self,msg):
    self.__log(logging.DEBUG,msg)

  def info(self,msg):
    self.__log(logging.INFO,msg)

  def warning(self,msg):
    self.__log(logging.WARNING,msg)

  def error(self,msg):
    self.__log(logging.ERROR,msg)

  def critical(self,msg):
    self.__log(logging.CRITICAL,msg)

  def getEffectiveLevel(self):
    return self.__get_logger().getEffectiveLevel()
