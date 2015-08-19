#!/usr/bin/env python
#
# Example advanced Sibyl bot

import logging,time

from jabberbot import botcmd
from sibylbot import SibylBot

# here we are creating a new class called Sibyl that extends SibylBot
# this lets us add new commands or override old commands
# later we will create a Sibyl instance rather than a SibylBot instance
# the string immediately following the declaration is displayed as "help"
class Sibyl(SibylBot):
  """https://github.com/TheSchwa/sibyl/wiki/Commands"""
  
  # you must include the @botcmd tag so JabberBot knows to create a hook;
  # mess is the actual xmpp message object, args is the text passed
  # by the user after the command name; if you return a string, the bot
  # will respond to the command with the string; the string immediately
  # after the definition will be listed by the "help" command
  
  @botcmd
  def time(self,mess,args):
    """return the current time"""
    
    return time.asctime()
    
  @botcmd
  def allmusic(self,mess,args):
    """play all music on my flash drive"""
    
    # XBMC JSON-RPC API: http://kodi.wiki/view/JSON-RPC_API/v6
    self.xbmc('Playlist.Clear',{'playlistid':0})
    self.xbmc('Playlist.Add',{'playlistid':0,'item':{'directory':'/media/SCHWA 16G/MUSIC'}})
    self.xbmc('Player.Open',{'item':{'playlistid':0}})
    self.xbmc('GUI.SetFullscreen',{'fullscreen':True})
  
  # here we will override the "hello" command to have the sender's nick
  @botcmd
  def hello(self,mess,args):
    """say hello back"""
    
    nick = mess.getFrom()
    nick = nick[nick.rfind('/')+1:]
    return 'Hello '+nick+'!'

# XMPP parameters
# set ROOMPASS to None for no password
RPI_IP = '192.168.1.3'
USERNAME = 'user@example.com'
PASSWORD = 'mypassword'
CHATROOM = 'room@conference.example.com'
ROOMPASS = 'roompass'

# if you set a username and password on the XBMC webserver
XBMC_USER = 'username'
XBMC_PASS = 'password'

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
# below is my personal configuration for Sibyl
# explanations of every option: https://github.com/TheSchwa/sibyl/wiki/API#class-sibylbot

# nick_name is the bot's MUC nick (default is "Sibyl")
# audio_dirs and video_dirs allow searching and playing media
# xbmc_user and xbmc_pass are only needed if set on XBMC's webserver
# you should always set 'log_file', 'lib_file', and 'bm_file'
# max_matches=0 is useful for XMPP servers with pastebin support
# chat_ctrl=True enables the "reboot" and "kill" commands
bot = Sibyl(USERNAME,PASSWORD,rpi_ip=RPI_IP,
    nick_name='SibylBot'
    audio_dirs=AUDIODIRS,
    video_dirs=VIDEODIRS,
    xbmc_user=XBMC_USER,
    xbmc_pass=XBMC_PASS,
    log_file='/var/log/sibyl.log'
    lib_file='/home/pi/bin/sibyl_lib.pickle',
    bm_file='/home/pi/bin/sibyl_bm.txt',
    max_matches=0,
    chat_ctrl=True)

# set logging level to debug
bot.log.setLevel(logging.DEBUG)

bot.muc_join_room(CHATROOM,bot.nick_name,password=ROOMPASS)
bot.serve_forever()
