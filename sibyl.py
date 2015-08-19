#!/usr/bin/env python
#
# Example Sibyl bot

from sibylbot import SibylBot

# XMPP parameters
# set ROOMPASS to None for no password
RPI_IP = ''
USERNAME = 'user@example.com'
PASSWORD = 'mypassword'
CHATROOM = 'room@conference.example.com'
ROOMPASS = 'roompass'

# example samba share definitio
# set 'username' or 'password' to None as necessary
smb_theschwa_videos = ({'server':'THESCHWA',
                        'share':'videos',
                        'username':'user',
                        'password':'pass'})

# audio library paths
AUDIODIRS = (['/media/SCHWA 16G/MUSIC'])

# video library paths
VIDEODIRS = (['/home/pi/mnt/sshfs',
              '/media/usbdrive/videos',
              smb_theschwa_videos])

# only_direct means users in the MUC must preface commands with "sibyl"
# you can change the bot's nick by specifying nick_name here (default: 'Sibyl')
# the 3 parameters on the first line are required, the rest are optional
bot = SibylBot(USERNAME,PASSWORD,rpi_ip=RPI_IP,
    only_direct=True,
    audio_dirs=AUDIODIRS,
    video_dirs=VIDEODIRS)

bot.join_room(CHATROOM,bot.nick_name,password=ROOMPASS)
bot.serve_forever()
