# Sibyl
an XMPP bot for controlling XBMC/Kodi

**IMPORTANT: Sibly is in Alpha. Updates may break existing configurations**

**IMPORTANT: The wiki is currently outdated. Updates coming soon.**

## Intro
This is my personal XMPP bot made mostly for controlling XBMC on my Raspberry Pi. I find the `videos`, `seek`, `info`, `bookmark`, and `resume` commands to be very handy. This is tested on RaspBMC and OSMC, but should work on anything if you resolve the dependencies and setup python correctly. Sibyl does not support windows, although you could probably get it working via cygwin. Sibyl imports chat commands from python files in the directory specified by the `cmd_dir` config option, which by default is `cmds`. This repository comes with several plugins that most uers should find useful. For command explanations and other info check out [the wiki][1]. Currently sibyl is built assuming the bot is running on the same device that is running XBMC (e.g. an RPi).

## Dependencies
You'll need the following installed in order to use sibyl:
 - [xmpppy][10] - XMPP python API - `git clone https://github.com/normanr/xmpppy.git`
 - [requests][3] - HTTP request and wrapper library - `pip install requests`
 - [smbc][4] - python samba bindings - `pip install pysmbc`
 - [lxml][9] - xml and html parsing - `pip install lxml`
 - [dns][11] - required for requests - `pip install dnspython`
 - [JSON-RPC][6] - you have to enable the web server in XBMC

The following are optional but not having them may render some commands broken:
 - [cec-client][5] - HDMI CEC client for tv commands

One-liner for Ubuntu/Debian:
 - `sudo apt install python-xmpp python-requests python-smbc python-lxml python-dnspython`

## Setup
Setup is very easy, all you really have to do is make a config file.

 1. Clone the repository with `git clone https://github.com/TheSchwa/sibyl.git`
 2. Install dependencies (see above)
 3. Enter the `sibyl` directory and copy `sibyl.conf.default` to `sibyl.conf`
 4. Edit `sibyl.conf` and set the required options `username` and `password`
 5. If you want the bot to join a room set `rooms` in the `JabberBot` section
 6. If starting Sibyl from the command line, add its parent directory to your `PYTHONPATH`
 7. Start the bot with `python run.py`
 8. For a full explanation of config options, see `sibyl.conf.default` or [the wiki][1]

If you'd rather not have comments cluttering your config, here is an example config file with common options:

```
username = sibyl@server.com
password = wordpass
rooms = room@conference.server.com
cmd_prefix = !

xbmc_ip = 127.0.0.1
audio_dirs = /mnt/flashdrive/music
video_dirs = /mnt/harddrive/videos;
             mediaserver,Videos,username,password

admin_cmds = config,die,join,leave,log,reboot,xbmc
admin_usrs = admin@server.com,someone@server.com
bw_list = b %(admin_cmds)s *;
          w * %(admin_usrs)s;
```

## XBMC/Kodi
Sibyl interfaces with XBMC using its JSON-RPC web interface. In order to use it, you must enable the web server in XBMC (see the link in the Dependencies section). Therefore, for `xbmc` plug-in commands, the bot does not actually have to be running on the Pi. It just needs to be able to reach the Pi's HTTP interface. The `library` plug-in commands, however, do assume the bot is running on the same box as XBMC. Plesae note the port on which the web server is running when you activate it. For example, you might set `xbmc_ip = 127.0.0.1:8080` in the config.

## CEC
Sibyl uses the `cec-client` bash script to give commands over HDMI-CEC to an attached TV. This should be installed on most Pi distros by default. If not, debian derivatives can install with `sudo apt-get install cec-client`. For the CEC commands to work, the bot must be running on the Pi itself. Also note that `cec-client` may not be found depending on your environment. On my Pi it's located at `/home/pi/.xbmc-current/xbmc-bin/bin/cec-client`. Depending on your distro, the user running Sibyl might need to be a member of the `videos` group or similar to run `cec-client`.

## Search Directories
You can add folders to `video_dirs` and `audio_dirs` in order to search them using the `search`, `audio`, `audios`, `video`, and `videos` commands. This functionality is provided by the `library.py` plug-in. You can add the following as list items:
  - local directory, example: `/media/flashdrive/videos`
  - samba share as `server,share`, example: `mediaserver,videos`
  - samba share as `server,share,user,pass`, example: `mediaserver,videos,pi,1234`

Also be aware that root cannot read `sshfs` mounts from other users by default. If this is a problem with your setup, you have to specify `sshfs -o allow_root ...` when you mount the share as a non-root user. I do not recommend running sibyl as root.

## Init Script
For Debian and derivates I include an init script, `sibyl.init` and the actual execution script `sibyl.sh`. You will have to change the `DAEMON` variable in `sibyl.init` to the absolute path of `sibyl.sh`. You have to rename `sibyl.init` to `sibyl` and place it in `/etc/init.d` for compliance with Debian's init system. If your distro uses systemd, you may have to run `sudo systemctl daemon-reload`. If your distro does not use systemd, to enable auto-start on boot, run `sudo update-rc.d sibyl defaults`.

As currently configured, the init script starts the bot with the user `sibyl`. You can make this user for example with `sudo adduser sibyl` and then clone the repo into that user's home directory. If you don't want the script to start as the `sibyl` user, change `-c sibyl`  to `-c user` from the below line in the init script. If you remove `-c sibyl` entirely, the bot will run as root. Despite my attempts to keep Sibyl safe, I do not recommend running it as root. Do so at your own risk.

`if start-stop-daemon --start --quiet -c sibyl --oknodo --pidfile $PIDFILE --exec $DAEMON ; then`

## Logging
By default, sibyl logs to `data/sibyl.log` which can be changed with the `log_file` option. To enable debug logging, simply set the config option `log_level = debug`. To print XMPP stanzas to the terminal, set `debug = True`.

## Contact Me
If you have a bug report or feature request, use github's issue tracker. For other stuff, you can join my Sibyl XMPP room `sibyl@conference.jahschwa.com`, the IRC channel `chat.freenode.net#sibyl`, or contact me at [haas.josh.a@gmail.com][8].

 [1]: https://github.com/TheSchwa/sibyl/wiki
 [2]: https://thp.io/2007/python-jabberbot/
 [3]: http://docs.python-requests.org/en/latest/
 [4]: https://bitbucket.org/nosklo/pysmbclient/src/057512c24175?at=default
 [5]: http://libcec.pulse-eight.com/
 [6]: http://kodi.wiki/view/Webserver#Enabling_the_webserver
 [7]: https://github.com/antont/pythonjabberbot/tree/master/examples
 [8]: mailto:haas.josh.a@gmail.com
 [9]: http://lxml.de/
 [10]: http://xmpppy.sourceforge.net/
 [11]: http://www.dnspython.org/
