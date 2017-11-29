# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2017 Joshua Haas <jahschwa.com>
#
# JabberBot: A simple jabber/xmpp bot framework
# Copyright (c) 2007-2012 Thomas Perl <thp.io/about>
# $Id: d1c7090edd754ff0da8ef4eb10d4b46883f34b9f $
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
#
# botcmd    - chat commands
# botfunc   - helper functions
# botinit   - bot initialisation
# botdown   - bot shutdown
# botcon    - successfully connected to server
# botdiscon - disconnected from server
# botrecon  - attempting to reconnect to server
# botrooms  - successfully joined a room
# botroomf  - failed to join a room
# botstatus - received a STATUS update
# boterr    - received an ERROR message
# botmsg    - received a PRIVATE or GROUP message
# botpriv   - received a PRIVATE message
# botgroup  - received a GROUP message
# botidle   - about once per second
# botconf   - add options to parse from the config file
# botsend   - called when a message is sent
#
# Full explanations: https://github.com/TheSchwa/sibyl/wiki/Plug-Ins
#
################################################################################

# decorated function: func(bot,mess,args)
# @param bot (SibylBot)
# @param mess (Message) triggering Message
# @param args (list) not including the command name itself
def botcmd(*args,**kwargs):
  """Decorator for bot chat commands"""

  # @param name (str) [function name] the name to respond to in chat
  # @param ctrl (bool) [False] whether to restrict the command with "chat_ctrl"
  # @param hidden (bool) [False] whether to hide this command from help output
  # @param thread (bool) [False] whether to thread the command
  # @param raw (bool) [False] if True don't parse args; pass original text
  def decorate(func,name=None,ctrl=False,hidden=False,thread=False,raw=False):
    setattr(func, '_sibylbot_dec_chat', True)
    setattr(func, '_sibylbot_dec_chat_name', name or func.__name__)
    setattr(func, '_sibylbot_dec_chat_ctrl', ctrl)
    setattr(func, '_sibylbot_dec_chat_hidden', hidden)
    setattr(func, '_sibylbot_dec_chat_thread', thread)
    setattr(func, '_sibylbot_dec_chat_raw', raw)
    return func

  if len(args):
    return decorate(args[0],**kwargs)
  else:
    return lambda func: decorate(func,**kwargs)

# decorated function: no required signature
def botfunc(func):
  """Decorator for bot helper functions"""

  setattr(func, '_sibylbot_dec_func', True)
  return func

# decorated function: func(bot)
# @param bot (SibylBot)
def botinit(func):
  """Decorator for bot initialisation hooks"""

  setattr(func, '_sibylbot_dec_init', True)
  return func

# decorated function: func(bot)
# @param bot (SibylBot)
def botdown(func):
  """Decorator for bot closing functions"""

  setattr(func, '_sibylbot_dec_down', True)
  return func

# decorated function: func(bot)
# @param bot (SibylBot)
def botcon(func):
  """Decorator for bot connection hooks"""

  setattr(func, '_sibylbot_dec_con', True)
  return func

# decorated function: func(bot,ex)
# @param bot (SibylBot)
# @param ex (Exception) the reason the bot disconnected
def botdiscon(func):
  """Decorator for bot disconnection hooks"""

  setattr(func, '_sibylbot_dec_discon', True)
  return func

# decorated function: func(bot)
# @param bot (SibylBot)
def botrecon(func):
  """Decorator for bot reconnection hooks"""

  setattr(func, '_sibylbot_dec_recon', True)
  return func

# decorated function: func(bot,room)
# @param bot (SibylBot)
# @param room (str) room we successfully connected to
def botrooms(func):
  """Decorator for success joining a room hooks"""

  setattr(func, '_sibylbot_dec_rooms', True)
  return func

# decorated function: func(bot,room,err)
# @param bot (SibylBot)
# @param room (str) the room we failed to connect to
# @param err (str) the human-readable reason we failed
def botroomf(func):
  """Decorator for failure to join a room hooks"""

  setattr(func, '_sibylbot_dec_roomf', True)
  return func

# decorated function: func(bot,mess)
# @param bot (SibylBot)
# @param mess (Message) the STATUS Message received
def botstatus(func):
  """Decorator for status received hooks"""

  setattr(func, '_sibylbot_dec_status', True)
  return func

# decorated function: func(bot,mess)
# @param bot (SibylBot)
# @param mess (Message) the ERROR Message received
def boterr(func):
  """Decorator for error received hooks"""

  setattr(func, '_sibylbot_dec_err', True)
  return func

# decorated function: func(bot,mess,cmd)
# @param bot (SibylBot)
# @param mess (Message) the PRIVATE or GROUP Message received
# @param cmd (str,None) the cmd+args that will be executed or None if no cmd
def botmsg(func):
  """Decorator for message received hooks"""

  setattr(func, '_sibylbot_dec_msg', True)
  return func

# decorated function: func(bot,mess,cmd)
# @param bot (SibylBot)
# @param mess (Message) the PRIVATE
# @param cmd (str,None) the cmd+args that will be executed or None if no cmd
def botpriv(func):
  """Decorator for private message received hooks"""

  setattr(func, '_sibylbot_dec_priv', True)
  return func

# decorated function: func(bot,mess,cmd)
# @param bot (SibylBot)
# @param mess (Message) the GROUP Message received
# @param cmd (str,None) the cmd+args that will be executed or None if no cmd
def botgroup(func):
  """Decorator for group message received hooks"""

  setattr(func, '_sibylbot_dec_group', True)
  return func

# decorated function: func(bot)
# @param bot (SibylBot)
def botidle(*args,**kwargs):
  """Decorator for idle hooks (executed once per second)"""

  # @param freq (int) [1] number of seconds to wait between executions
  # @param thread (bool) [False] whether to thread the command
  def decorate(func,freq=1,thread=False):
    setattr(func, '_sibylbot_dec_idle', True)
    setattr(func, '_sibylbot_dec_idle_freq', freq)
    setattr(func, '_sibylbot_dec_idle_thread', thread)
    return func

  if len(args):
    return decorate(args[0],**kwargs)
  else:
    return lambda func: decorate(func,**kwargs)

# decorated function: func(bot)
# @param bot (SibylBot)
# @return (list of dict) config options to add, dict defined below
#   name     (str)  [req]: name of the config option to read from the file
#   default  (obj)  [req]: default value of option (should be Python object)
#   req      (bool) [opt]: quit execution if option is missing (default: False)
#   parse    (func) [opt]: parse the given string into a Python object
#   valid    (func) [opt]: validate the given Python object
#   post     (func) [opt]: perform checks after all config opts have been parsed
#
# for more details: https://github.com/TheSchwa/sibyl/wiki/Plug-Ins
#
def botconf(func):
  """Decorator for bot helper functions"""

  setattr(func, '_sibylbot_dec_conf', True)
  return func

# decorated function: func(bot,mess)
# @param bot (SibylBot)
# @param msg (Message) the message being sent
#
# NOTE: if you use bot.send() inside here, you must have hook=False
def botsend(func):
  """Decorator for message sent hooks"""
  
  setattr(func, '_sibylbot_dec_send', True)
  return func
