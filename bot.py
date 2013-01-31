#!/usr/bin/env python
# Copyright 2012 Evan Hazlett
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import gevent
import json
import argparse
from redis import StrictRedis
from irc import IRCBot, run_bot
from gevent import monkey
import config
import logging

monkey.patch_all()

def get_redis_client():
    return StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT,
        db=config.REDIS_DB, password=config.REDIS_PASSWORD)
pub = get_redis_client()

class RelayBot(IRCBot):
    def __init__(self, *args, **kwargs):
        super(RelayBot, self).__init__(*args, **kwargs)
        gevent.spawn(self.do_sub)

    def do_sub(self):
        log = logging.getLogger()
        sub = get_redis_client()
        self.pubsub = sub.pubsub()
        self.pubsub.subscribe(config.REDIS_PUBSUB_CHANNEL)
        for msg in self.pubsub.listen():
            if msg['type'] != 'message':
                continue
            log.debug('Received {0}'.format(msg))
            for channel in config.IRC_CHANNELS:
                self.respond(msg['data'],
                    channel=channel)

    def do_privmsg(self, nick, message, channel): pass
    def do_part(self, nick, command, channel): pass
    def do_quit(self, command, nick, channel): pass
    def do_nick(self, old_nick, command, new_nick): pass
    def command_patterns(self):
        return (
            ('/privmsg', self.do_privmsg),
            ('/part', self.do_part),
            ('/quit', self.do_quit),
            ('/nick', self.do_nick),
        )

if __name__=='__main__':
    run_bot(RelayBot, config.IRC_HOST,
        config.IRC_PORT, config.IRC_NICK,
        config.IRC_CHANNELS)
