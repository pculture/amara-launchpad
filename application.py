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
from flask import (redirect, url_for, render_template, request, flash, session,
    json)
from flask.ext import redis
from flask.ext.babel import Babel
from flask.ext.mail import Mail
from rq_dashboard import RQDashboard
import config
import messages
import utils
import time
from utils import db, accounts, queue_task, ops
from accounts.views import accounts_blueprint
from admin.views import admin_blueprint

app = config.create_app()
app.register_blueprint(accounts_blueprint, url_prefix='/accounts')
app.register_blueprint(admin_blueprint, url_prefix='/admin')
babel = Babel(app)
mail = Mail(app)
redis = redis.init_redis(app)
# add exts for blueprint use
app.config['babel'] = babel
app.config['mail'] = mail
app.config['redis'] = redis
RQDashboard(app)

# check for admin user ; create if missing
if not db.get_user('admin'):
    print('Creating admin user; password: launchpad')
    db.create_user(username='admin', password='launchpad',
        email=config.ADMIN_EMAIL, is_admin=True)

# hack to add auth for rq dashboard
@app.before_request
def rq_auth_check():
    print(request.path)
    if request.path.find('/rq') > -1 and not session.get('user'):
        return redirect(url_for('accounts.login'))

@app.route('/')
def index():
    return redirect(url_for('admin.index'))

#github post receive hook
@app.route('/github', methods=['POST'])
def github_hook():
    data = json.loads(request.form.get('payload', ''))
    # make sure this came from unisubs
    repo = data.get('repository', {})
    if repo.get('name') == 'unisubs' and \
        repo.get('url') == 'https://github.com/pculture/unisubs':
        # get the branch
        branch = data.get('ref').split('refs/heads/')[-1]
        result_key = str(int(time.time()))
        db.log({
            'ip': request.remote_addr,
            'user': 'github',
            'command': 'Hook: deploy for {0}'.format(branch),
        })
        task = 'demo:amara,{0} deploy'.format(branch)
        print('Running {0}'.format(task))
        job = queue_task(ops.run_fabric_task, task, result_key)
    return 'kthxbye'

if __name__=='__main__':
    from optparse import OptionParser
    op = OptionParser()
    op.add_option('--host', dest='host', action='store', default='127.0.0.1', \
        help='Hostname/IP on which to listen')
    op.add_option('--port', dest='port', action='store', type=int, \
        default=5000, help='Port on which to listen')
    opts, args = op.parse_args()

    app.run(host=opts.host, port=opts.port, debug=True)
