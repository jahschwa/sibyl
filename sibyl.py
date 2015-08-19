#!/usr/bin/env python
#
# Example Sibyl bot

from sibylbot import SibylBot

# XMPP parameters
# set ROOMPASS to None for no password
RPI_IP = '192.168.1.3'
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

# the 3 parameters on the first line are required, the rest are optional
# audio_dirs and video_dirs allow searching and playing media
# you should always set 'log_file', 'lib_file', and 'bm_file'
bot = SibylBot(USERNAME,PASSWORD,rpi_ip=RPI_IP,
    audio_dirs=AUDIODIRS,
    video_dirs=VIDEODIRS,
    log_file='/home/pi/bin/sibyl.log'
    lib_file='/home/pi/bin/sibyl_lib.pickle',
    bm_file='/home/pi/bin/sibyl_bm.txt')

bot.muc_join_room(CHATROOM,bot.nick_name,password=ROOMPASS)
bot.serve_forever()
