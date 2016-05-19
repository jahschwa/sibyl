#!/usr/bin/env python

def botcmd(*args,**kwargs):
  """Decorator for bot chat commands"""

  def decorate(func,name=None,hidden=False):
    setattr(func, '_sibylbot_dec_chat', True)
    setattr(func, '_sibylbot_dec_chat_name', name or func.__name__)
    setattr(func, '_sibylbot_dec_chat_hidden', hidden)
    return func

  if len(args):
    return decorate(args[0],**kwargs)
  else:
    return lambda func: decorate(func,**kwargs)

def botfunc(func):
  """Decorator for bot helper functions"""

  setattr(func, '_sibylbot_dec_func', True)
  return func

def botinit(func):
  """Decorator for bot initialisation hooks"""

  setattr(func, '_sibylbot_dec_init', True)
  return func

def botmucs(func):
  """Decorator for success joining a room hooks"""

  setattr(func, '_sibylbot_dec_mucs', True)
  return func

def botmucf(func):
  """Decorator for failure to join a room hooks"""

  setattr(func, '_sibylbot_dec_mucf', True)
  return func

def botmsg(func):
  """Decorator for message received hooks"""

  setattr(func, '_sibylbot_dec_msg', True)
  return func

def botpres(func):
  """Decorator for presence received hooks"""

  setattr(func, '_sibylbot_dec_pres', True)
  return func

def botidle(func):
  """Decorator for idle hooks (executed once per second)"""

  setattr(func, '_sibylbot_dec_idle', True)
  return func

def botconf(func):
  """Decorator for bot helper functions"""

  setattr(func, '_sibylbot_dec_conf', True)
  return func
