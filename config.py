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
from utils import amara

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
# cache
CACHE_TYPE = 'redis'
CACHE_REDIS_HOST = REDIS_HOST
CACHE_REDIS_PORT = REDIS_PORT
CACHE_REDIS_PASSWORD = REDIS_PASSWORD
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

# workflows
# these are pre-configured workflows that allow non-admin users to run tasks
# with specific arguments
# wrapped in a function so the 'data' loaders are called each time

def get_workflows():
    branches = amara.get_repo_branches()
    branches.sort()
    return (
        {
            'name': 'Activate Integration Link',
            'category': 'Demo',
            'command': 'demo:amara,<revision> activate_integration_link',
            'arguments': [
                {
                    'name': 'revision',
                    'data': branches,
                }
            ]
        },
        {
            'name': 'Remove Integration Link',
            'category': 'Demo',
            'command': 'demo:amara,<revision> remove_integration_link',
            'arguments': [
                {
                    'name': 'revision',
                    'data': branches,
                }
            ]
        },
        {
            'name': 'Show Demos',
            'category': 'Demo',
            'command': 'demo:amara show_demos',
            'arguments': [],
        },
        {
            'name': 'Create Demo',
            'category': 'Demo',
            'command': 'demo:amara,<revision> create_demo:url_prefix=<url>',
            'arguments': [
                {
                    'name': 'revision',
                    'data': None,
                },
                {
                    'name': 'url',
                    'data': None,
                }
            ]
        },
        {
            'name': 'Create Demo from Branch',
            'category': 'Demo',
            'command': 'demo:amara,<revision> create_demo:url_prefix=<url>',
            'arguments': [
                {
                    'name': 'revision',
                    'data': branches,
                },
                {
                    'name': 'url',
                    'data': None,
                }
            ]
        },
        {
            'name': 'Delete Demo by Branch',
            'category': 'Demo',
            'command': 'demo:amara,<revision> remove_demo',
            'arguments': [
                {
                    'name': 'revision',
                    'data': branches,
                }
            ],
        },
        {
            'name': 'Delete Demo',
            'category': 'Demo',
            'command': 'demo:amara,<revision> remove_demo',
            'arguments': [
                {
                    'name': 'revision',
                    'data': None,
                }
            ],
        },
        {
            'name': 'Update Demo by Branch',
            'category': 'Demo',
            'command': 'demo:amara,<revision> deploy',
            'arguments': [
                {
                    'name': 'revision',
                    'data': branches,
                }
            ],
        },
        {
            'name': 'Update Virtualenv by Branch',
            'category': 'Demo',
            'command': 'demo:amara,<revision> update_environment',
            'arguments': [
                {
                    'name': 'revision',
                    'data': branches,
                }
            ],
        },
        {
            'name': 'Update Demo',
            'category': 'Demo',
            'command': 'demo:amara,<revision> deploy',
            'arguments': [
                {
                    'name': 'revision',
                    'data': None,
                }
            ],
        },
        {
            'name': 'Deploy',
            'category': 'Admin',
            'command': '<environment>:amara deploy',
            'arguments': [
                {
                    'name': 'environment',
                    'data': None,
                }
            ],
        },
        {
            'name': 'Test Services',
            'category': 'Test',
            'command': '<environment>:amara test_services',
            'arguments': [
                {
                    'name': 'environment',
                    'data': None,
                }
            ],
        }
    )
