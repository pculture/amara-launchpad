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
from flask import (Blueprint, render_template, request, url_for, redirect,
    flash, session, current_app)
from flaskext.babel import gettext
from decorators import admin_required, login_required
import utils
import config
from utils import db, ops, queue_task, generate_json_response
from ansi2html import Ansi2HTMLConverter
import messages
import time
from cache import cache

bp = admin_blueprint = Blueprint('admin', __name__,
    template_folder='templates')

def _convert_ansi(text, full=False):
    converted = ''
    try:
        conv = Ansi2HTMLConverter(markup_lines=True, linkify=True, escaped=False)
        converted = conv.convert(text.replace('\n', ' <br/>'), full=full)
    except Exception, e:
        converted = text
    return converted

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    workflows = config.get_workflows()
    job = None
    result_key = None
    workflow_id = None
    workflows = utils.sorted_dict(workflows, 'name')
    if request.method == 'POST':
        form = request.form
        workflow_id = form.get('workflow_id')
        if workflow_id:
            workflow = [x for x in workflows if x.get('name') == workflow_id][0]
            username = session.get('user', {}).get('username')
            db.log({
                'ip': request.remote_addr,
                'user': username,
                'command': 'Workflow: {0}'.format(workflow_id),
            })
            args = workflow.get('arguments')
            # substitute args
            task = workflow.get('command')
            if args:
                for a in args:
                    arg_name = a.get('name')
                    arg_val = form.get(arg_name, None)
                    task = task.replace('<{0}>'.format(arg_name),
                        form.get(arg_name))
            # add proxy_user to get launchpad user
            task = task.replace('<proxy_user>', username)
            # generate result_key
            result_key = str(int(time.time()))
            # run command
            job = queue_task(ops.run_fabric_task, task, result_key,
                workflow.get('notify'))
    ctx = {
        'workflows': workflows,
        'job': job,
        'result_key': result_key,
    }
    return render_template('admin/index.html', **ctx)

@bp.route('/console/', methods=['GET', 'POST'])
@admin_required
def console():
    task = ''
    job = None
    result_key = None
    if request.method == 'POST':
        form = request.form
        task = form.get('task')
        if task:
            result_key = str(int(time.time()))
            db.log({
                'ip': request.remote_addr,
                'user': session.get('user', {}).get('username'),
                'command': task
            })
            # run command
            job = queue_task(ops.run_fabric_task, task, result_key)
    ctx = {
        'task': task,
        'job': job,
        'result_key': result_key,
    }
    return render_template('admin/console.html', **ctx)

@bp.route('/tasks/<job_id>/results/<key>')
@login_required
def task_results(job_id=None, key=None):
    job_status = db.get_job_status(job_id)
    res = db.get_results(key)
    if res:
        res = _convert_ansi(res)
    else:
        res = gettext('Waiting for task to start...')
    # check for failed status
    if job_status == 'failed':
        res = gettext('Task failed.  Please check logs.')
    data = {
        'key': key,
        'results': res,
        'status': job_status,
    }
    return generate_json_response(data)

@bp.route('/logs/<key>/')
@login_required
def get_log(key=None):
    return _convert_ansi(ops.get_fabric_log(key))

