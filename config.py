#!/usr/bin/env python
# Copyright 2012 Participatory Culture Foundation
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
from flask import Flask
import logging

APP_NAME = 'launchpad'
APP_VERSION = '0.1'
ADMIN_EMAIL = None
FABRIC_PREFIX = '' # prefix for every fabric command (no spaces between options)
LOG_DIR = '/tmp'
LOG_LEVEL = logging.DEBUG
MAIL_SERVER = 'localhost'
MAIL_PORT = 25
MAIL_USE_TLS = False
MAIL_USE_SSL = False
MAIL_USERNAME = None
MAIL_PASSWORD = None
DEFAULT_SENDER = 'launchpad@local'
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None
RESULT_TTL = 86400 # task result TTL
SECRET_KEY = '1q2w3e4r5t6y7u8i9o0p'
# local config
try:
    from local_config import *
except ImportError:
    pass

def create_app():
    """
    Flask app factory

    :rtype: `flask.Flask`

    """
    app = Flask(__name__)
    app.config.from_object('config')
    return app

