# sibyl
an XMPP bot for controlling XBMC/Kodi on the Raspberry PI

## Dependencies
You'll need the following installed in order to use sibyl:
 - [jabberbot][1] - extensible XMPP bot using xmpppy - `pip install jabberbot` or `sudo apt-get install python-jabberbot`
 - [requests][2] - HTTP request and wrapper library - `pip install requests` or `sudo apt-get install python-requests`
 - [smbc][3] - python bindings for smbclient - `pip install pysmbc` or `sudo apt-get install python-smbc`

## JabberBot
By default sibyl is setup to join an XMPP MUC (i.e. group chat) but you can change that if you want. Refer to the [examples directory][4] for JabberBot. Adding additional commands is easy as well. Simply define a new method inside the `GrandBot` class and preface it with `@botcmd` to register the command.

Note that there is currently a bug in JabberBot. It does not correctly ignore message from itself when in a MUC. This is fixed naievly in sibyl by simply searching for `NICKNAME` in the from field of XMPP replies. Therefore, as currently implemented, any user whose name contains sibyl's `NICKNAME` will be ignored.

## XBMC/Kodi
Sibyl interfaces with XBMC using its JSON-RPC web interface. In order to use it, you must enable the web server in XBMC as described [here][5].

## CEC
Sibyl uses the `cec-client` bash script to give commands over HDMI-CEC to an attached TV. This should be installed on most Pi distros by default. If not, debian derivatives can install with `sudo apt-get install cec-client`.

## Search Directories
You can add folders to `VIDEODIRS` and `AUDIODIRS` in order to search them using the `audio`, `audios`, `video`, and `videos` commands. You can add the following as list items:
  - local directory, example: `'/media/flashdrive/videos'`
  - samba share, example: `('smb://HOSTNAME/videos',do_auth_hostname)`

Samba shares protected by passowrd require an authentication function. An example is given in `sibyl.py`.

## Init Script
For Debian and derivates I include an init script, `sibyl.init` and the actual execution script `sibyl`. Note that if you want to use these you may have to change the `DAEMON` variable in `sibyl.init`. In my setup, `sibyl.init` is in `/etc/init.d/`, `sibyl` is in `/home/pi/bin`, and `sibyl.py` is in `/home/pi/bin`.

## Logging
By default, sibyl logs to `/var/log/sibyl.log`. To enable debug logging, simply uncomment the debug line in `main()`.

## Known Bugs
 - Sibyl will randomly crash without logging a stacktrace (please report this so I can figure it out!)

 [1]: https://thp.io/2007/python-jabberbot/
 
 [3]: http://cyberelk.net/tim/software/pysmbc/
 [4]: https://github.com/antont/pythonjabberbot/tree/master/examples
 [5]: http://kodi.wiki/view/Webserver#Enabling_the_webserver
