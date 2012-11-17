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
from random import Random
import string
from utils import get_redis_connection, db
import config

RESET_CODE_KEY = 'reset_codes:{0}'

def create_reset_code(username=None):
    code = ''.join(Random().sample(string.letters+string.digits, 24))
    rds = get_redis_connection()
    key = RESET_CODE_KEY.format(code)
    rds.set(key, username)
    rds.expire(key, getattr(config, 'RESET_CODE_TTL', 3600))
    return code

def get_user_from_code(code=None):
    rds = get_redis_connection()
    key = RESET_CODE_KEY.format(code)
    user = None
    if key:
        user = db.get_user(rds.get(key))
    return user

def delete_reset_code(code=None):
    rds = get_redis_connection()
    key = RESET_CODE_KEY.format(code)
    return rds.delete(key)
