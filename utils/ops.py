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
import config
import subprocess
import os
import sys
from utils import db

def run_fabric_task(cmd=None, result_key=None):
    if not cmd:
        raise ValueError('You must specify args')
    cmd_args = cmd.split()
    cmd_args.insert(0, 'fab')
    os.environ['PYTHONUNBUFFERED'] = 'true'
    p = subprocess.Popen(cmd_args, stdout=subprocess.PIPE)
    # only store results if requested
    if result_key:
        for line in iter(p.stdout.readline, ''):
            db.add_results(result_key, line)
    p.wait()
    return '{0} complete'.format(cmd)
