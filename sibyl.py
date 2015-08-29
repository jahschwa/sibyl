#!/usr/bin/env python
#
# Example Sibyl bot

from sibylbot import SibylBot
import config

# the 3 parameters on the first line are required, the rest are optional
# audio_dirs and video_dirs allow searching and playing media
# you should always set 'log_file', 'lib_file', and 'bm_file'
bot = SibylBot(config.USERNAME,config.PASSWORD,rpi_ip=config.RPI_IP,
    audio_dirs=config.AUDIODIRS,
    video_dirs=config.VIDEODIRS,
    log_file=config.LOG_FILE,
    lib_file=config.LIB_FILE,
    bm_file=config.BM_FILE)

# if you don't want the bot to join a MUC just call the method without
# any parameters; omit the third option if the MUC has no password
bot.run_forever(config.CHATROOM,bot.nick_name,config.ROOMPASS)
