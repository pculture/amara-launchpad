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
import utils
from utils import get_redis_connection
from flask import json
import time

USER_KEY = 'users:{0}'
RESULT_KEY = 'results:{0}'
RQ_JOB_KEY = 'rq:job:{0}'
LOG_KEY = 'logs'

def create_user(username=None, password='', email=None, is_admin=False):
    """
    Creates a new user

    :param username: Username of user
    :param password: User password
    :param email: User email
    :param is_admin: Admin user

    """
    rds = get_redis_connection()
    data = {
        'username': username,
        'password': utils.hash_text(password),
        'email': email,
        'is_admin': is_admin,
    }
    return rds.set(USER_KEY.format(username), json.dumps(data))

def get_user(username=None):
    """
    Returns a user object from the datastore

    :param username: Username

    """
    rds = get_redis_connection()
    data = rds.get(USER_KEY.format(username))
    if data:
        data = json.loads(data)
    return data

def get_all_users():
    """
    Returns all users

    """
    rds = get_redis_connection()
    users = []
    user_keys = rds.keys(USER_KEY.format('*'))
    [users.append(json.loads(rds.get(x))) for x in user_keys]
    return users

def update_user(username=None, data={}):
    """
    Updates a user with the specified data

    :param username: Username to update
    :param data: Data to update as a dict

    """
    rds = get_redis_connection()
    user_data = rds.get(USER_KEY.format(username))
    ret = None
    if user_data:
        user = json.loads(user_data)
        for k,v in data.iteritems():
            # hash password if present
            if k == 'password':
                v = utils.hash_text(v)
            user[k] = v
        ret = rds.set(USER_KEY.format(username), json.dumps(user))
    return ret


def delete_user(username=None):
    """
    Deletes a user

    :param username: Username to delete

    """
    rds = get_redis_connection()
    return rds.delete(USER_KEY.format(username))

def add_results(key=None, text=''):
    """
    Stores (appends) result output

    :param key: Key (for retrieval)

    """
    rds = get_redis_connection()
    return rds.append(RESULT_KEY.format(key), text)

def get_results(key=None):
    """
    Gets result output

    :param key: Command key

    """
    rds = get_redis_connection()
    return rds.get(RESULT_KEY.format(key))

def get_job_status(job_id=None):
    """
    Gets an RQ job status

    :param job_id: Job ID

    """
    rds = get_redis_connection()
    return rds.hget(RQ_JOB_KEY.format(job_id), 'status')

def log(data={}):
    """
    Logs item to DB

    :param data: Log data as dict

    """
    if not isinstance(data, dict):
        data = {'log': data}
    data['date'] = int(time.time())
    rds = get_redis_connection()
    return rds.lpush(LOG_KEY, json.dumps(data))

