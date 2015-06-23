# sibyl
an XMPP bot for controlling XBMC/Kodi on the Raspberry Pi

## Intro
This is my personal XMPP bot made mostly for controlling XBMC on my Raspberry Pi. I find the `videos`, `seek`, and `info` commands to be very handy. This is tested on RaspBMC, but should work on anything if you resolve the dependencies and setup python correctly. For command explanations and other info check out the wiki.

## Dependencies
You'll need the following installed in order to use sibyl:
 - [jabberbot][1] - XMPP bot using xmpppy - `pip install jabberbot` or `sudo apt-get install python-jabberbot`
 - [requests][2] - HTTP request and wrapper library - `pip install requests` or `sudo apt-get install python-requests`
 - [smbc][3] - python bindings for smbclient - `pip install pysmbc` or `sudo apt-get install python-smbc`
 - [cec-client][4] - HDMI CEC client - `sudo apt-get install libcec`
 - [JSON-RPC][5] - enable the web server in XBMC

## Setup
First set the global variables in `sibyl.py`. Enter the IP of the Raspberry Pi (an internal LAN IP should be fine) in `RPI_IP`. The XMPP login info for the bot should go in `USERNAME` and `PASSWORD`. The XMPP MUC info goes in `NICKNAME`, `CHATROOM`, and `ROOMPASS`. If the room doesn't have a password you can just set `ROOMPASS` to `None`. If you want to use the `video(s)` or `audio(s)` commands, remove the examples and add paths to `VIDEODIRS` and `AUDIODIRS`. If any of those paths are samba shares, you'll need to make auth functions for them. See the "Search Directories" section for an example.

## JabberBot
By default sibyl is setup to join an XMPP MUC (i.e. group chat) but you can change that if you want. Refer to the [examples directory][6] for JabberBot. Adding additional commands is easy as well. Simply define a new method inside the `GrandBot` class and preface it with `@botcmd` to register the command.

Note that there is currently a bug in JabberBot. It does not correctly ignore message from itself when in a MUC. This is fixed naievly in sibyl by simply searching for `NICKNAME` in the from field of XMPP replies. Therefore, as currently implemented, any user whose name contains sibyl's `NICKNAME` will be ignored.

## XBMC/Kodi
Sibyl interfaces with XBMC using its JSON-RPC web interface. In order to use it, you must enable the web server in XBMC (see the link in the Dependencies section). Therefore, for these commands, the bot does not actually have to be running on the Pi. It just needs to be able to reach the Pi's HTTP interface..

## CEC
Sibyl uses the `cec-client` bash script to give commands over HDMI-CEC to an attached TV. This should be installed on most Pi distros by default. If not, debian derivatives can install with `sudo apt-get install cec-client`. For the CEC commands to work, the bot must be running on the Pi.

## Search Directories
You can add folders to `VIDEODIRS` and `AUDIODIRS` in order to search them using the `audio`, `audios`, `video`, and `videos` commands. You can add the following as list items:
  - local directory, example: `'/media/flashdrive/videos'`
  - samba share, example: `('smb://HOSTNAME/videos',do_auth_hostname)`

Samba shares protected by passowrd require an authentication function. Here's the format:

    def do_auth(svr,shr,wg,un,pw):
      return ('WORKGROUP','username','password')

Also be aware that root cannot read `sshfs` mounts from other users by default. If this is a problem with your setup (e.g. I run sibyl as `root` via the init script, but the `sshfs` mount requires the `pi` user's pubkey), you have to specify `sshfs -o allow_root ...` when you mount the share as a non-root user.

## Init Script
For Debian and derivates I include an init script, `sibyl.init` and the actual execution script `sibyl`. Note that if you want to use these you may have to change the `DAEMON` variable in `sibyl.init`. In my setup, `sibyl.init` is in `/etc/init.d/`, `sibyl` is in `/home/pi/bin`, and `sibyl.py` is in `/home/pi/bin`.

## Logging
By default, sibyl logs to `/var/log/sibyl.log`. To enable debug logging, simply uncomment the debug line in `main()`.

## Known Bugs
 - Sibyl will randomly crash without logging a stacktrace (please report this so I can figure it out!)

## Contact Me
If you have a bug report or feature request, use github's issue tracker. For other stuff, you can contact me at [haas.josh.a@gmail.com][7].

 [1]: https://thp.io/2007/python-jabberbot/
 [2]: http://docs.python-requests.org/en/latest/
 [3]: http://cyberelk.net/tim/software/pysmbc/
 [4]: http://libcec.pulse-eight.com/
 [5]: http://kodi.wiki/view/Webserver#Enabling_the_webserver
 [6]: https://github.com/antont/pythonjabberbot/tree/master/examples
 [7]: mailto:haas.josh.a@gmail.com
