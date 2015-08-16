#!/usr/bin/env python
#
# Example Sibyl bot

import logging

from sibylbot import SibylBot

# XMPP parameters
# set ROOMPASS to None for no password
RPI_IP = ''
USERNAME = 'user@example.com'
PASSWORD = 'mypassword'
CHATROOM = 'room@conference.example.com'
ROOMPASS = 'roompass'

# example samba authentication method
smb_theschwa_videos = ({'server':'THESCHWA',
                        'share':'videos',
                        'username':'user',
                        'password':'pass'})

# audio library paths
AUDIODIRS = (['/media/SCHWA 16G/MUSIC'])

# video library paths
VIDEODIRS = (['/home/pi/mnt/tardis',
              '/home/pi/mnt/area11',
              smb_theschwa_videos])

bot = SibylBot(USERNAME,PASSWORD,rpi_ip=RPI_IP,only_direct=True,
    audio_dirs=AUDIODIRS,video_dirs=VIDEODIRS)

bot.join_room(CHATROOM,bot.nick_name,password=ROOMPASS)
bot.serve_forever()
