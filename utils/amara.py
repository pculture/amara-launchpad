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
import requests
try:
    import simplejson as json
except ImportError:
    import json

def get_repo_branches():
    # get repo branches from github
    branch_url = 'https://api.github.com/repos/pculture/unisubs/branches'
    resp = requests.get(branch_url)
    branches = []
    if resp.status_code == 200:
        try:
            data = json.loads(resp.content)
            [branches.append(x.get('name')) for x in data \
                if x.get('name').startswith('x-')]
        except Exception, e:
            print('Unable to parse Github branch data: {0}'.format(e))
    return branches
