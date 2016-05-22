# Sibyl Change Log
All notable changes to this project will be documented in this file.
To the full project is at the [Github Repo](https://github.com/TheSchwa/Sibyl).
This project adheres to [Semantic Versioning](http://semver.org).
This change log follows guidelines at [this site](http://keepachangelog.com/).

## [v6.0.0] - RELEASEDATE
### Added
- Chat plug-in framework that reads from "protocols" directory
- Custom protocol-agnostic msg and presence classes with methods
- XMPP plug-in (based on Jabberbot) at protocols/xmpp.py
- Matrix plug-in at protocols/matrix.py
- New decorators: botcon, botdiscon, botrecon, botdown
- New chat cmd "tell" in room.py
### Changed
- All decorators are now located in decorators.py
- Chat commands now receive their args as a list (possibly empty)
- Quote blocking now works for all commands (also preserves capitalization)
- Decorator: botpres to botstatus
- Moved config.py, decorators.py, protocol.py, and util.py to new directory lib

### Removed
- Refactored jabberbot.py into protocols/xmpp.py and sibylbot.py

### Changed
- All decorators are now in sibylbot.py

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
- Custom jabberbot.py

### Changed
- Change from pysmbc to pysmbclient

## [v1.0.0-alpha] - 2015-06-26
### Added
- Refactoring into sibylbot.py

## [v0.0.0-alpha] - 2015-06-22
### Added
- Basic chat bot for controlling XBMC in sibyl.py

[Unreleased]: https://github.com/TheSchwa/sibyl/tree/dev
[v5.0.0-beta]: https://github.com/TheSchwa/sibyl/compare/v4.0.0-beta...v5.0.0-beta
[v4.0.0-beta]: https://github.com/TheSchwa/sibyl/compare/v3.0.0-beta...v4.0.0-beta
[v3.0.0-beta]: https://github.com/TheSchwa/sibyl/compare/v2.0.0-alpha...v3.0.0-beta
[v2.0.0-alpha]: https://github.com/TheSchwa/sibyl/compare/v1.0.0-alpha...v2.0.0-alpha
[v1.0.0-alpha]: https://github.com/TheSchwa/sibyl/compare/v0.0.0-alpha...v1.0.0-alpha
[v0.0.0-alpha]: https://github.com/TheSchwa/sibyl/commit/3470c49
