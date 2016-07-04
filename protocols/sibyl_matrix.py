#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Sibyl: A modular Python chat bot framework
# Copyright (c) 2015-2016 Joshua Haas <jahschwa.com>
# Copyright (c) 2016 Jonathan Frederickson <jonathan@terracrypt.net>
#
# This file is part of Sibyl.
#
# Sibyl is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
################################################################################

from lib import protocol
from lib.decorators import botconf
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError

@botconf
def conf(bot):
  return {'name':'server','default':None, 'req': True}


class MXID(protocol.User):

    mxid = ''

    def parse(self, mxid, typ):
        self.mxid = mxid
        self.set_real(mxid)

    def get_name(self):
        print("TODO stuff")
        #TODO: Display name calculation

    def get_room(self):
        return self.room_id

    def get_base(self):
        return self.mxid

    def __eq__(self, other):
        if(self.get_base() == other.get_base()):
            return True
        else:
            return False

    def __str__(self):
        return self.mxid

class Matrix(protocol.Protocol):

    def setup(self):
        self.connected = False
        self.rooms = {}

    def connect(self):
        homeserver = self.opt('server')
        user = self.opt('username')
        pw = self.opt('password')

        self.log.debug("Connecting to %s" % homeserver)
        self.client = MatrixClient(homeserver)

        token = ""

        try:
            self.log.debug("Logging in as %s" % user)
            self.token = self.client.login_with_password(user, pw)
            self.rooms = self.client.get_rooms()
            self.log.debug("Already in rooms: %s" % self.rooms)
            self.connected = True
            self.client.add_listener(self._cb_message)
        except MatrixRequestError as e:
            self.log.error(e)
            if(e.code == 403):
                raise protocol.AuthFailure
            else:
                raise protocol.ConnectFailure

    def is_connected(self):
        print("TODO: is_connected()")
        return self.connected

    def disconnected(self):
        print("TODO: disconnected()")

    def process(self):
        self.client.listen_for_events(timeout=1000)

    def shutdown(self):
        print("TODO: shutdown()")

    def send(self, text, to):
        print("TODO: send()")

    def broadcast(self, text, room, frm=None):
        print("TODO: broadcast()")

    def join_room(self, room, nick, pword=None):
        # TODO: Keep rooms variable up to date
        if(self.in_room(room)):
            self.log.info("Already in room %s" % room)
            self.bot._cb_join_room_success
        else:
            self.log.info("Joining room %s" % room)
            ret = self.client.join_room(room)
            if(ret != None):
                self.bot._cb_join_room_success
                self.rooms[ret.room_id] = ret
            else:
                self.bot._cb_join_room_failure

    def part_room(self, room):
        print("TODO: part_room")

    def in_room(self, room):
        for roomid, existing_room in self.rooms.items():
            if(room[0] == '#'):
                if(room in existing_room.aliases):
                    return True
            elif(room[0] == '!'):
                if(room == roomid):
                    return True
        return False

    def get_rooms(self, in_only=False):
        print("TODO: get_rooms")

    def get_occupants(self, room):
        print("TODO: get_occupants")

    def get_nick(self, room):
        print("TODO: get_nick")

    def get_real(self, room, nick):
        print("TODO: get_real")

    def new_user(self, user, typ):
        print("TODO: new_user")

    def _cb_message(self, event):
        self.log.debug(event)
        if(event['type'] == 'm.room.message'):
            room = event['room_id']
            if(self.in_room(room)):
                self.log.debug(event['content']['body'])
