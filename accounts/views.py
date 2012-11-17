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
from flask import (request, render_template, flash, redirect,
    url_for, session, current_app, Response, json, Blueprint)
from utils import db, hash_text
import utils
from decorators import login_required, admin_required
import messages

bp = accounts_blueprint = Blueprint('accounts', __name__,
    template_folder='templates')

@bp.route('/login/', methods=['GET', 'POST'])
def login():
    username = ''
    if request.method == 'POST':
        form = request.form
        username = form.get('username')
        u = db.get_user(username)
        if u:
            if hash_text(form.get('password')) == u.get('password'):
                # login
                session['user'] = u
                return redirect(url_for('admin.index'))
        flash(messages.INVALID_USERNAME_PASSWORD, 'error')
    ctx = {'username': username}
    return render_template('accounts/login.html', **ctx)

@bp.route('/create/', methods=['POST'])
@admin_required
def create():
    form = request.form
    username = form.get('username')
    email = form.get('email')
    if username and email:
        db.create_user(username=username, email=email)
        flash(messages.USER_CREATED, 'success')
    else:
        flash(messages.EMPTY_USERNAME_EMAIL, 'error')
    return redirect(url_for('admin.index'))

@bp.route('/delete')
@bp.route('/delete/<username>')
@admin_required
def delete(username=None):
    if username:
        db.delete_user(username)
        flash(messages.USER_DELETED, 'success')
    return redirect(url_for('admin.index'))

@bp.route('/change-password/', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        form = request.form
        username = session.get('user').get('username')
        password = form.get('password')
        if form.get('password') != form.get('password_confirm'):
            flash(messages.PASSWORDS_NOT_MATCH, 'error')
            return redirect(url_for('accounts.change_password'))
        db.update_user(username, {'password': password})
        # reset session
        session['user'] = None
        flash(messages.PASSWORD_UPDATED, 'success')
        return redirect(url_for('index'))
    ctx = {}
    return render_template('accounts/change_password.html', **ctx)

@bp.route('/logout/')
@login_required
def logout():
    session['user'] = None
    flash(messages.LOGGED_OUT, 'info')
    return redirect(url_for('index'))

