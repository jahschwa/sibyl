# Sibyl Change Log
All notable changes to this project will be documented in this file.
To the full project is at the [Github Repo](https://github.com/TheSchwa/Sibyl).
This project adheres to [Semantic Versioning](http://semver.org).
This change log follows guidelines at [this site](http://keepachangelog.com/).

## [Unreleased]
### Added
- Actual change log tracking
- Chat protocol plug-in framework that reads from `protocols` directory
- Protocol-agnostic `Message` and `Room` classes with methods in `protocols.py`
- XMPP plug-in (based on Jabberbot) at `protocols/sibyl_xmpp.py`
- Matrix plug-in at `protocols/sibyl_matrix.py`
- Command line client plug-in at `protocols/sibyl_cli.py`
- Socket plug-in at `protocols/sibyl_socket.py`
- Decorators: botcon, botdiscon, botrecon, botdown, boterr, botpriv, botgroup
- Ability to specify "chat_ctrl" cmds with `@botcmd(ctrl=True)`
- Ability to execute chat commands in a separate thread with `@botcmd(thread=True)`
- Made `bot.send()` threadsafe
- New chat cmd "tell" in `room.py` to give messages once a user joins the room
- New chat cmd "about" in `sibylbot.py`to give info about the bot
- Checking for duplicate plugin (file) names
- Checking for duplicate config options from different plugins
- New config option `enable` to enable only a specific list of plugins
- New config option `disable` to disable plugins (supersedes `enable`)
- New config option `help_plugin` that displays plugin names in help list
- New config options `log_requests` and `log_urllib3` to enable logging
- New config options `persistence` and `state_file` for use with `bot.add_var`
- New config option `general.config_room` to disable `config` command in rooms
- New config option `room.cross_proto` to disable using `room` commands across protocols
- Disabled `stdout`; all plugins should use logging instead
- Plugins can specify dependencies as a list via the `__depends__` variable
- Plugins can specify "wants" as a list via the `__wants__` variable
- New `@botconf` key `post` for validating against other config options
- Some basic unit tests (more to follow)
- Support for running multiple protocols in the same sibyl instance
- New class `Password` in `lib/password.py` for obfuscating config options from the `config` chat cmd
- New class `Log` in `lib/log.py` to automate `logging.Logger` names
- New started file for devs writing protocols in `protocols/skeleton.py`
- Added new `example` dir for user and dev examples
- Added example plugin `example/alarm.py`
- Added example configuation file `example/sibyl.conf`
- Added example of python threading `example/thread.py`
- Some `room.py` commands (`all`, `join`, `leave`, `say`) now accept a protocol name

### Changed
- License changed from GPLv2 to GPLv3
- All decorators are now in `lib/decorators.py`
- Chat commands now receive their args as a list (possibly empty)
- Quote blocking now works for all commands (also preserves capitalization)
- Decorator: `botpres` is now `botstatus`
- Moved `config.py`, `decorators.py`, `protocol.py`, `sibylbot.py`, `util.py` to dir `lib`
- Moved `sibyl.init` and `sibyl.sh` to dir `init`
- Pinging is now enabled by default for xmpp
- If a @botidle hook raises an exception, it will be disabled forever
- The `reboot` command no longer requires init setup (now works entirely inside python)
- Chat commands are now case insensitive
- Config names now automatically start with the name of the plug-in (e.g. xbmc.ip)
- The `config` command automatically obfuscates any config option whose name ends with `password`
- Rebuilding the library is now done in a separate (non-blocking) process
- Renamed plugin `muc.py` to `room.py`
- The `prev` command from `xbmc.py` now jumps to playlist position instead of using the JSON-RPC built-in
- Sibyl now catches `SIGTERM` and exits cleanly
- All imports must now start with `sibyl`
- The `log` command now has log viewing functionality

### Removed
- Refactored `jabberbot.py` into `protocols/sibyl_xmpp.py` and `lib/sibylbot.py`

## [v5.0.0-beta] - 2016-05-18
### Added
- Recursive cmd plug-in search

### Changed
- Option `rpi_ip` to `xbmc_ip`
- Switch back from pysmbclient to pysmbc

## [v4.0.0-beta] - 2016-04-04
### Added
- Chat command plug-in framework
- Additional decorators

## [v3.0.0-beta] - 2016-03-30
### Added
- Actual config file

## [v2.0.0-alpha] - 2016-01-30
### Added
- Custom `jabberbot.py`

### Changed
- Change from `pysmbc` to `pysmbclient`

## [v1.0.0-alpha] - 2015-06-26
### Added
- Refactoring into `sibylbot.py`

## [v0.0.0-alpha] - 2015-06-22
### Added
- Basic chat bot for controlling XBMC in `sibyl.py`

[Unreleased]: https://github.com/TheSchwa/sibyl/tree/dev
[v5.0.0-beta]: https://github.com/TheSchwa/sibyl/compare/v4.0.0-beta...v5.0.0-beta
[v4.0.0-beta]: https://github.com/TheSchwa/sibyl/compare/v3.0.0-beta...v4.0.0-beta
[v3.0.0-beta]: https://github.com/TheSchwa/sibyl/compare/v2.0.0-alpha...v3.0.0-beta
[v2.0.0-alpha]: https://github.com/TheSchwa/sibyl/compare/v1.0.0-alpha...v2.0.0-alpha
[v1.0.0-alpha]: https://github.com/TheSchwa/sibyl/compare/v0.0.0-alpha...v1.0.0-alpha
[v0.0.0-alpha]: https://github.com/TheSchwa/sibyl/commit/3470c49
