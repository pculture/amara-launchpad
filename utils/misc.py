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
import os
from fabric.api import sudo, env, run
from fabric.context_managers import hide
from flask import current_app, json, Response, request
from flask.ext.mail import Message
import tempfile
from redis import Redis
import hashlib
import config
from rq import Queue

def get_redis_connection():
    """
    Returns a Redis connection

    """
    try:
        rds = current_app.config.get('redis')
    except:
        rds = Redis(host=getattr(config, 'REDIS_HOST'),
            port=getattr(config, 'REDIS_PORT'),
            db=getattr(config, 'REDIS_DB'),
            password=getattr(config, 'REDIS_PASSWORD'))
    return rds

def queue_task(func, *args, **kwargs):
    q = Queue(connection=get_redis_connection())
    return q.enqueue_call(func=func, args=args, kwargs=kwargs,
        result_ttl=getattr(config, 'RESULT_TTL', 300), timeout=1800)

def hash_text(text):
    """
    Hashes text with app key

    :param text: Text to encrypt

    """
    h = hashlib.sha256()
    h.update(getattr(config, 'SECRET_KEY'))
    h.update(text)
    return h.hexdigest()

def generate_json_response(data, status=200, content_type='application/json'):
    """
    `flask.Response` factory for JSON response

    :param data: Data that gets serialized to JSON
    :param status: Status code (default: 200)
    :param content_type: Content type (default: application/json)

    """
    indent = None
    if request.args.get('indent'):
        indent = 2
    # check if need to add status_code
    if data == type({}) and not data.has_key('status_code'):
        data['status_code'] = status
    # serialize
    if type(data) != type(''):
        data = json.dumps(data, sort_keys=True, indent=indent)
    resp = Response(data, status=status, content_type=content_type)
    return resp

def send_mail(subject=None, text=None, to=[]):
    """
    Sends mail

    :param subject: Subject
    :param text: Message
    :param to: Recipients as list

    """
    mail = current_app.config.get('mail')
    msg = Message(subject, sender=current_app.config.get('DEFAULT_SENDER'), \
        recipients=to)
    msg.body = text
    return mail.send(msg)

