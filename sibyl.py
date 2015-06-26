#!/usr/bin/env python
#
# Example Sibyl bot

import logging

import sibylbot

# XMPP parameters
# set ROOMPASS to None for no password
RPI_IP = ''
USERNAME = 'user@example.com'
PASSWORD = 'mypassword'
CHATROOM = 'room@conference.example.com'
ROOMPASS = 'roompass'

# samba authentication methods

def do_auth_theschwa(svr,shr,wg,un,pw):
  return ('WORKGROUP','username','password')

# search path lists, items can be:
#  - local: '/media/SCHWA 16G/MUSIC'
#  - samba: ('smb://THESCHWA/videos',do_auth_theschwa)

AUDIODIRS = (['/media/SCHWA 16G/MUSIC'])

VIDEODIRS = (['/home/pi/mnt/tardis',
              '/home/pi/mnt/area11',
              ('smb://THESCHWA/videos',do_auth_theschwa)])

bot = SibylBot(USERNAME,PASSWORD,only_direct=True,rpi_ip=RPI_IP,
    audio_dirs=AUDIODIRS,video_dirs=VIDEODIRS)

#bot.log.setLevel(logging.DEBUG)

bot.join_room(CHATROOM,bot.nick_name,password=ROOMPASS)
bot.serve_forever()
