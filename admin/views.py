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
from flask import Blueprint, render_template, request, url_for, redirect, flash
from decorators import admin_required, login_required
from utils import db, ops, queue_task, generate_api_response
from ansi2html import Ansi2HTMLConverter
import messages
import time

bp = admin_blueprint = Blueprint('admin', __name__,
    template_folder='templates')

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    task = ''
    job = None
    result_key = None
    if request.method == 'POST':
        form = request.form
        task = form.get('task')
        if task:
            result_key = str(int(time.time()))
            # run command
            job = queue_task(ops.run_fabric_task, task, result_key)
    ctx = {
        'task': task,
        'job': job,
        'result_key': result_key,
    }
    return render_template('admin/index.html', **ctx)

@bp.route('/tasks/<job_id>/results/<key>')
@login_required
def task_results(job_id=None, key=None):
    job_status = db.get_job_status(job_id)
    conv = Ansi2HTMLConverter(markup_lines=True, escaped=False)
    res = db.get_results(key)
    if res:
        res = conv.convert(res.replace('\n', ' <br/>'), full=False)
    data = {
        'key': key,
        'results': res,
        'status': job_status,
    }
    return generate_api_response(data)

