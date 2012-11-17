# Amara, universalsubtitles.org
#
# Copyright (C) 2012 Participatory Culture Foundation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see
# http://www.gnu.org/licenses/agpl-3.0.html.
from __future__ import with_statement

import os, sys, string, random
from datetime import datetime
from functools import wraps
import time

import fabric.colors as colors
from fabric.api import run, sudo, env, cd, local as _local, abort, task, put
from fabric.tasks import execute
from fabric.context_managers import settings, hide
from fabric.utils import fastprint
from fabric.decorators import roles, runs_once, parallel
import fabric.state
try:
    import simplejson as json
except:
    import json

ADD_TIMESTAMPS = """ | awk '{ print strftime("[%Y-%m-%d %H:%M:%S]"), $0; fflush(); }' """
WRITE_LOG = """ | tee /tmp/%s.log """

# hide 'running' by default
fabric.state.output['running'] = False

# Output Management -----------------------------------------------------------
PASS_THROUGH = ('sudo password: ', 'Sorry, try again.')
class CustomFile(file):
    def __init__(self, *args, **kwargs):
        self.log = ""
        return super(CustomFile, self).__init__(*args, **kwargs)

    def _record(self, s):
        self.log = self.log[-255:] + s.lower()

        if any(pt in self.log for pt in PASS_THROUGH):
            sys.__stdout__.write('\n\n' + self.log.rsplit('\n', 1)[-1])
            self.log = ""

    def write(self, s, *args, **kwargs):
        self._record(s)
        return super(CustomFile, self).write(s, *args, **kwargs)


_out_log = CustomFile('fabric.log', 'w')
class Output(object):
    """A context manager for wrapping up standard output/error nicely.

    Basic usage:

        with Output("Performing task foo"):
            ...

    This will print a nice header, redirect all output (except for password
    prompts) to a log file, and then unredirect the output when it's finished.

    If you need to override the redirection inside the body, you can use the
    fastprint and fastprintln methods on the manager:

        with Output("Performing task foo") as out:
            ...
            if something:
                out.fastprintln('Warning: the disk is getting close to full.')
            ...

    WARNING: Do not nest 'with Output(...)' blocks!  I have no idea how that
    will behave at the moment.  This includes calling a function that contains
    an Output block from within an Output block.

    TODO: Fix this.

    """
    def __init__(self, message=""):
        host = '({0})'.format(env.host) if env.host else ''
        self.message = '{0} {1}'.format(message, host)

    def __enter__(self):
        if self.message:
            fastprint(colors.white(self.message.ljust(60) + " -> ", bold=True))

        sys.stdout = _out_log
        sys.stderr = _out_log

        if self.message:
            fastprint("\n\n")
            fastprint(colors.yellow("+" + "-" * 78 + "+\n", bold=True))
            fastprint(colors.yellow("| " + self.message.ljust(76) + " |\n", bold=True))
            fastprint(colors.yellow("+" + "-" * 78 + "+\n", bold=True))
        return self

    def __exit__(self, type, value, tb):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        if type is None:
            fastprint(colors.green("OK\n", bold=True))
        else:
            fastprint(colors.red("FAILED\n", bold=True))
            fastprint(colors.red(
                "\nThere was an error.  "
                "See ./fabric.log for the full transcript of this run.\n",
                bold=True))

    def fastprint(self, s):
        sys.stdout = sys.__stdout__
        fastprint(s)
        sys.stdout = _out_log

    def fastprintln(self, s):
        self.fastprint(s + '\n')

def _notify(subj, msg, to):
    env.host_string = env.dev_host
    run("echo '{1}' | mailx -s '{0}' {2}".format(subj, msg, to))

def _lock(*args, **kwargs):
    """
    Creates a temporary "lock" file to prevent concurrent deployments

    """
    with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
        res = run('cat {0}'.format(env.deploy_lock))
    if res.succeeded:
        abort('Another operation is currently in progress: {0}'.format(res))
    else:
        task = kwargs.get('task', '')
        with settings(hide('running', 'stdout', 'stderr'), warn_only=True):
            run('echo "{0} : {1}" > {2} {3}'.format(datetime.now(), env.user, env.deploy_lock, task))

def _unlock(*args, **kwargs):
    """
    Removes deploy lock

    """
    with settings(hide('running', 'stdout', 'stderr'), warn_only=True):
        run('rm -f {0}'.format(env.deploy_lock))

def lock_required(f):
    """
    Decorator for the lock / unlock functionality

    """
    @wraps(f)
    def decorated(*args, **kwargs):
        _lock()
        out = None
        try:
            out = f(*args, **kwargs)
        except:
            pass
        finally:
            _unlock()
        return out
    return decorated

@task
@roles('app', 'data')
def remove_lock():
    """
    Removes lock from hosts (in the event of a failed task)

    """
    with Output('Removing lock'):
        _unlock()

def _local(*args, **kwargs):
    '''Override Fabric's local() to facilitate output logging.'''
    capture = kwargs.get('capture')

    kwargs['capture'] = True
    out = _local(*args, **kwargs)

    if capture:
        return out
    else:
        print out

def _create_env(username,
                name,
                s3_bucket,
                app_name,
                app_dir,
                app_group,
                builder_host,
                lb_host,
                revision,
                ve_dir,
                app_server_ami_id,
                separate_uslogging_db,
                key_filename=env.key_filename,
                roledefs={},
                notification_email=None):
    env.user = username
    env.name = name
    env.environment = name
    env.s3_bucket = s3_bucket
    env.app_name = app_name
    env.app_dir = app_dir
    env.app_group = app_group
    env.builder_host = builder_host
    env.lb_host = lb_host
    env.revision = revision
    env.ve_dir = ve_dir
    env.app_server_ami_id = app_server_ami_id
    env.separate_uslogging_db = separate_uslogging_db
    env.key_filename = key_filename
    env.roledefs = roledefs
    env.deploy_lock = '/tmp/.amara_deploy_{0}'.format(revision)
    env.notification_email = notification_email or 'universalsubtitles-dev@pculture.org'
    env.password = os.environ.get('FABRIC_PASSWORD', None)
    env.dev_host = 'dev.universalsubtitles.org'
    env.build_apps_root = '/opt/media_compile/apps'
    env.build_ve_root = '/opt/media_compile/ve'
    env.demo_domain = 'demo.amara.org'
    env.jenkins_host = 'dev.universalsubtitles.org'
    env.jenkins_jobs_dir = '/var/lib/jenkins/jobs'
    env.lb_config = '/etc/nginx/conf.d/unisubs.{0}.conf'.format(env.environment)
    env.scaling_aws_key = 'pcf_ec2_keys_amara'
    env.scaling_instance_type = 'm1.medium'
    env.scaling_security_groups = ['amara-app', 'amara-core']

@task
def local(username='vagrant', key='~/.vagrant.d/insecure_private_key'):
    """
    Configure task(s) to run in the local environment

    """
    with Output("Configuring task(s) to run on LOCAL"):
        _create_env(username              = username,
                    name                  = 'local',
                    s3_bucket             = 's3.local.amara.org',
                    app_name              = 'unisubs',
                    app_dir               = '/opt/apps/local/unisubs/',
                    app_group             = 'deploy',
                    builder_host          = 'app.local',
                    lb_host               = 'lb.local',
                    revision              = 'staging',
                    ve_dir                = '/opt/ve/local/unisubs',
                    app_server_ami_id     = None,
                    separate_uslogging_db = False,
                    key_filename          = key,
                    roledefs              = {
                        'app': ['10.10.10.115'],
                        'data': ['10.10.10.120'],
                    },
                    notification_email   = 'ehazlett@pculture.org',)
        env.dev_host = '10.10.10.115'

@task
def dev(username):
    """
    Configure task(s) to run in the dev environment

    """
    with Output("Configuring task(s) to run on DEV"):
        env_name = 'dev'
        _create_env(username              = username,
                    name                  = env_name,
                    s3_bucket             = None,
                    app_name              = 'unisubs',
                    app_dir               = '/opt/apps/{0}/unisubs/'.format(
                        env_name),
                    app_group             = 'deploy',
                    builder_host          = 'app-00-dev.amara.org',
                    lb_host               = None,
                    revision              = env_name,
                    ve_dir                = '/opt/ve/{0}/unisubs'.format(
                        env_name),
                    app_server_ami_id     = None,
                    separate_uslogging_db = False,
                    roledefs              = {
                        'app': ['app-00-dev.amara.org'],
                        'data': ['data-00-dev.amara.org'],
                    },
                    notification_email   = 'ehazlett@pculture.org',)

@task
def demo(username, revision=''):
    """
    Configure task(s) to run in the demo environment

    :param username: Username
    :param revision: Revision of demo

    """
    with Output("Configuring task(s) to run on DEMO {0}".format(revision)):
        hosts = {
            'app': 'app-00-dev.amara.org',
            'data': 'data-00-dev.amara.org',
        }
        env.demo_hosts = hosts
        env_name = 'demo'
        _create_env(username              = username,
                    name                  = env_name,
                    s3_bucket             = None,
                    app_name              = 'unisubs',
                    app_dir               = '/var/tmp/{0}/unisubs/'.format(
                        revision),
                    app_group             = 'deploy',
                    builder_host          = 'app-00-dev.amara.org',
                    lb_host               = None,
                    revision              = revision,
                    ve_dir                = '/var/tmp/{0}/ve'.format(
                        revision),
                    app_server_ami_id     = None,
                    separate_uslogging_db = False,
                    roledefs              = {
                        'app': ['app-00-dev.amara.org'],
                        'data': ['data-00-dev.amara.org'],
                    },
                    notification_email   = 'ehazlett@pculture.org',)

@task
def staging(username):
    """
    Configure task(s) to run in the staging environment

    """
    with Output("Configuring task(s) to run on STAGING"):
        env_name = 'staging'
        _create_env(username              = username,
                    name                  = env_name,
                    s3_bucket             = 's3.staging.amara.org',
                    app_name              = 'unisubs',
                    app_dir               = '/opt/apps/{0}/unisubs/'.format(
                        env_name),
                    app_group             = 'deploy',
                    builder_host          = 'app-00-dev.amara.org',
                    lb_host               = 'lb-staging.amara.org',
                    revision              = env_name,
                    ve_dir                = '/opt/ve/{0}/unisubs'.format(
                        env_name),
                    app_server_ami_id     = 'ami-4a843f23',
                    separate_uslogging_db = False,
                    roledefs              = {
                        'app': [
                            'app-00-staging.amara.org',
                            'app-01-staging.amara.org',
                        ],
                        'data': ['data-00-staging.amara.org'],
                    },
                    notification_email   = 'ehazlett@pculture.org',)
        # override default instance type
        env.scaling_instance_type = 'm1.small'

@task
def production(username):
    """
    Configure task(s) to run in the production environment

    """
    with Output("Configuring task(s) to run on PRODUCTION"):
        env_name = 'production'
        _create_env(username              = username,
                    name                  = env_name,
                    s3_bucket             = 's3.production.amara.org',
                    app_name              = 'unisubs',
                    app_dir               = '/opt/apps/{0}/unisubs/'.format(
                        env_name),
                    app_group             = 'deploy',
                    builder_host          = 'app-00-dev.amara.org',
                    lb_host               = 'lb-production.amara.org',
                    revision              = env_name,
                    ve_dir                = '/opt/ve/{0}/unisubs'.format(
                        env_name),
                    app_server_ami_id     = 'ami-70843f19',
                    separate_uslogging_db = False,
                    roledefs              = {
                        'app': [
                            'app-00-production.amara.org',
                            'app-01-production.amara.org',
                            'app-02-production.amara.org',
                            'app-03-production.amara.org',
                            'app-04-production.amara.org',
                        ],
                        'data': ['data-00-production.amara.org'],
                    },
                    notification_email   = 'ehazlett@pculture.org',)

def _reset_permissions(app_dir):
    sudo('chgrp -R {0} {1}'.format(env.app_group, app_dir))
    sudo('chmod -R g+w {0}'.format(app_dir))

@task
@roles('app', 'data')
def reset_permissions():
    _reset_permissions(env.app_dir)
    _reset_permissions(env.ve_dir)
    # reset builder dir
    env.host_string = env.builder_host

def _git_pull():
    run('git checkout --force')
    run('git pull --ff-only')
    run('chgrp {0} -R .git 2> /dev/null; /bin/true'.format(env.app_group))
    run('chmod g+w -R .git 2> /dev/null; /bin/true')
    _reset_permissions('.')

def _git_checkout(commit, as_sudo=False):
    cmd = run
    if as_sudo:
        cmd = sudo
    cmd('git fetch')
    cmd('git checkout --force %s' % commit)
    cmd('chgrp {0} -R .git 2> /dev/null; /bin/true'.format(env.app_group))
    cmd('chmod g+w -R .git 2> /dev/null; /bin/true')
    _reset_permissions('.')

def _git_checkout_branch_and_reset(commit, branch='dev', run_as_sudo=False):
    cmd = run
    if run_as_sudo:
        cmd = sudo
    if not branch:
        branch = env.revision
    cmd('git fetch')
    cmd('git checkout %s' % branch)
    cmd('git reset --hard %s' % commit)
    cmd('chgrp {0} -R .git 2> /dev/null; /bin/true'.format(env.app_group))
    cmd('chmod g+w -R .git 2> /dev/null; /bin/true')
    _reset_permissions('.')

def _get_optional_repo_version(app_dir, repo):
    '''Find the optional repo version by looking at its file in optional/.'''
    with cd(os.path.join(app_dir, 'optional')):
        return run('cat {0}'.format(repo))

@task
@lock_required
@runs_once
@roles('app')
def syncdb(extra=''):
    """Run python manage.py syncdb for the main and logging databases"""

    with Output("Syncing database") as out:
        with cd(env.app_dir):
            _git_pull()
            cmd = '{0}/bin/python manage.py syncdb {1} --settings=unisubs_settings'.format(\
                env.ve_dir, extra)
            #run('{0}/bin/python manage.py syncdb '
            #    '--settings=unisubs_settings'.format(env.ve_dir))
            run(cmd, pty=True)
            if env.separate_uslogging_db:
                run('{0}/bin/python manage.py syncdb '
                    '--database=uslogging --settings=unisubs_settings'.format(
                        env.ve_dir))
@task
@lock_required
@runs_once
@roles('app')
def migrate(app_name='', extra=''):
    with Output("Performing migrations"):
        with cd(env.app_dir):
            _git_pull()
            if env.separate_uslogging_db:
                run('{0}/bin/python manage.py migrate uslogging '
                    '--database=uslogging --settings=unisubs_settings'.format(
                        env.ve_dir))

            manage_cmd = 'yes no | {0}/bin/python -u manage.py migrate {1} {2} --settings=unisubs_settings 2>&1'.format(env.ve_dir, app_name, extra)
            timestamp_cmd = ADD_TIMESTAMPS.replace("'", r"\'")
            log_cmd = WRITE_LOG % 'database_migrations'

            cmd = (
                "screen sh -c $'" +
                    manage_cmd +
                    timestamp_cmd +
                    log_cmd +
                "'"
            )
            run(cmd)

@task
@roles('app', 'data')
def update_environment(extra=''):
    with Output('Updating environment'):
        with cd(os.path.join(env.app_dir, 'deploy')):
            if env.environment == 'demo':
                _git_checkout_branch_and_reset(
                    env.revision,
                    branch='dev',
                    run_as_sudo=True
                )
            else:
                _git_pull()
            run('export PIP_REQUIRE_VIRTUALENV=true')
            # see http://lincolnloop.com/blog/2010/jul/1/automated-no-prompt-deployment-pip/
            run('yes i | {0}/bin/pip install {1} -r requirements.txt'.format(env.ve_dir, extra), pty=True)
            _reset_permissions(env.app_dir)
        with cd(env.app_dir):
            run('{0}/bin/python deploy/create_commit_file.py'.format(env.ve_dir))

def _enable_lb_node(name=None):
    """
    Enables a node in the LB

    """
    if env.lb_host:
        old_host = name
        with settings(warn_only=True):
            env.host_string = env.lb_host
            sudo("sed -i 's/server {0}.*/server {0};/g' {1}".format(
                name, env.lb_config))
            sudo('service nginx reload')
        env.host_string = old_host

def _disable_lb_node(name=None):
    """
    Disables a node in the LB

    """
    if env.lb_host:
        old_host = name
        with settings(warn_only=True):
            env.host_string = env.lb_host
            sudo("sed -i 's/server {0}.*/server {0} down;/g' {1}".format(
                name, env.lb_config))
            sudo('service nginx reload')
        env.host_string = old_host

def _reload_app_servers(hard=False):
    with Output("Reloading application servers"):
        """
        Reloading the app server will both make sure we have a
        valid commit guid (by running the create_commit_file)
        and also that we make the server reload code (currently
        with mod_wsgi this is touching the wsgi file)
        """
        if hard:
            if env.environment == 'demo':
                script = 'uwsgi.unisubs.demo.{0}'.format(env.revision)
            else:
                script = 'uwsgi.unisubs.{0}'.format(env.environment)
            sudo('service {0} restart'.format(script))
        else:
            with cd(env.app_dir):
                run('{0}/bin/python deploy/create_commit_file.py'.format(env.ve_dir))
                run('touch deploy/unisubs.wsgi')
        # disable node on LB
        _disable_lb_node(env.host_string)
        with settings(warn_only=True):
            run('wget -q -T 120 --delete-after http://{0}/en/'.format(env.host_string))
        _enable_lb_node(env.host_string)

@task
@roles('app')
def reload_app_servers(hard=False):
    _reload_app_servers(hard)

# Maintenance Mode
@task
@roles('app')
def add_disabled():
    with Output("Putting the site into maintenance mode"):
        run('touch {0}/disabled'.format(env.app_dir))

@task
@roles('app')
def remove_disabled():
    with Output("Taking the site out of maintenance mode"):
        run('rm {0}/disabled'.format(env.app_dir))

def _update_integration(run_as_sudo=True, branch='dev', app_dir=None):
    if not app_dir:
        app_dir = env.app_dir
    with Output("Updating integration repository"):
        with cd(os.path.join(app_dir, 'unisubs-integration')), \
            settings(warn_only=True):
            _git_checkout_branch_and_reset(
                _get_optional_repo_version(app_dir, 'unisubs-integration'),
                branch=branch,
                run_as_sudo=run_as_sudo
            )
@task
@roles('app', 'data')
def update_integration(run_as_sudo=True, branch=None):
    '''Update the integration repo to the version recorded in the site repo.

    At the moment it is assumed that the optional/unisubs-integration file
    exists, and that the unisubs-integration repo has already been cloned down.

    The file should contain the commit hash and nothing else.

    TODO: Run this from update_web automatically

    '''
    _update_integration(run_as_sudo, branch)

def _update_solr_schema():
    python_exe = '{0}/bin/python'.format(env.ve_dir)
    with cd(env.app_dir):
        if env.environment == 'demo':
            _git_checkout_branch_and_reset(
                env.revision,
                branch='dev',
                run_as_sudo=True
            )
        else:
            _git_pull()
        sudo('{0} manage.py build_solr_schema --settings=unisubs_settings > /etc/solr/conf/{1}/conf/schema.xml'.format(
                python_exe,
                env.revision))
        sudo('service tomcat6 restart')
        run('{0} manage.py reload_solr_core --settings=unisubs_settings'.format(python_exe))

    # Fly, you fools!

    managepy_file = os.path.join(env.app_dir, 'manage.py')

    # The -u here is for "unbuffered" so the lines get outputted immediately.
    manage_cmd = '%s -u %s rebuild_index_ordered -v 2 --noinput --settings=unisubs_settings 2>&1' % (python_exe, managepy_file)
    mail_cmd = ' | mail -s \"Solr Index Rebuilt (%s) on %s\" %s' % (env.revision, env.host_string, env.notification_email)
    log_cmd = WRITE_LOG % 'solr_reindexing'

    # The single quotes in the ack command needs to be escaped, because
    # we're in a single quoted ANSI C-style string from the sh -c in the
    # screen command.
    #
    # We can't use a double quoted string for the sh -c call because of the
    # $0 in the ack script.
    timestamp_cmd = ADD_TIMESTAMPS.replace("'", r"\'")

    cmd = (
        "screen -d -m sh -c $'" +
            manage_cmd +
            timestamp_cmd +
            log_cmd +
            mail_cmd +
        "'"
    )

    run(cmd, pty=False)

@task
@lock_required
@runs_once
@roles('data')
def update_solr_schema():
    '''Update the Solr schema and rebuild the index.

    The rebuilding will be done asynchronously with screen and an email will
    be sent when it finishes.

    '''
    with Output("Updating Solr schema (and rebuilding the index)"):
        execute(_update_solr_schema)

def _bounce_memcached():
    with Output("Bouncing memcached"):
        # use nohup because ssh will terminate before memcached is restarted
        sudo('nohup /etc/init.d/memcached restart &')

@task
@roles('data')
def bounce_memcached():
    '''Bounce memcached (purging the cache).

    Should be done at the end of each deploy.

    '''
    _bounce_memcached()

def _bounce_celery():
    with Output("Bouncing celeryd"):
        with settings(warn_only=True):
            # use stop, then start separate because upstart is stupid
            sudo('service celeryd.{0} stop'.format(env.revision))
            sudo('service celeryd.{0} start'.format(env.revision))
    with Output("Bouncing celerycam"):
        with settings(warn_only=True):
            sudo('service celerycam.{0} stop'.format(env.revision))
            sudo('service celerycam.{0} start'.format(env.revision))

@task
@roles('data')
def bounce_celery():
    '''Bounce celery daemons.

    Should be done at the end of each deploy.

    '''
    _bounce_celery()

def _update_code(branch=None, integration_branch=None, app_dir=None):
    if not app_dir:
        app_dir = env.app_dir
    with Output("Updating the main unisubs repo"), cd(app_dir):
        if branch:
            _switch_branch(branch, app_dir=app_dir)
        else:
            _git_pull()
        run('python deploy/create_commit_file.py')
    # update integration repo
    _update_integration(branch=integration_branch, app_dir=app_dir)
    with cd(app_dir):
        with settings(warn_only=True):
            run("find . -name '*.pyc' -delete")

def _update_virtualenv(app_dir=None, ve_dir=None):
    if not app_dir:
        app_dir = env.app_dir
    if not ve_dir:
        ve_dir = env.ve_dir
    with Output("Updating virtualenv"), cd(os.path.join(app_dir, 'deploy')):
        sudo('yes i | {0}/bin/pip install -r requirements.txt'.format(ve_dir), pty=True)

@roles('app', 'data')
def update_code(branch=None, integration_branch=None):
    _update_code(branch=branch, integration_branch=integration_branch)

@task
def test_memcached():
    """Ensure memcached is running, working, and sane"""
    with Output("Testing memcached"):
        alphanum = string.letters+string.digits
        initial_host = env.roledefs['app'][0]
        env.host_string = initial_host
        random_string = ''.join(
            [alphanum[random.randint(0, len(alphanum)-1)]
            for i in xrange(12)])
        with cd(env.app_dir):
            run('{0}/bin/python manage.py set_memcached {1} --settings=unisubs_settings'.format(
                env.ve_dir, random_string))
        other_hosts = env.roledefs['app'][1:]
        for host in other_hosts:
            env.host_string = host
            output = ''
            with cd(env.app_dir):
                output = run('{0}/bin/python manage.py get_memcached --settings=unisubs_settings'.format(
                    env.ve_dir))
            if output.find(random_string) == -1:
                raise Exception('Machines {0} and {1} are using different memcached instances'.format(
                    initial_host, host))
@task
@roles('data')
def test_celeryd():
    """
    Ensures celeryd is running
    
    """
    with Output("Testing Celery"):
        out = run('ps aux | grep "{0}manage.py celeryd"|grep -v grep'.format(env.app_dir))
        assert len(out.split('\n'))

@task
@roles('app')
def test_app_services():
    """
    Runs test_services in application

    """
    with Output("Testing other services"):
        with cd(env.app_dir):
            run('{0}/bin/python manage.py test_services --settings=unisubs_settings'.format(
                env.ve_dir))

@task
def test_services():
    """
    Tests supporting services (memcached, celery, etc.)

    """
    execute(test_memcached)
    execute(test_celeryd)
    execute(test_app_services)

@task
def deploy(branch=None, integration_branch=None, skip_celery=False,
    skip_media=False):
    """
    This is how code gets reloaded:

    - Checkout code on the auxiliary server ADMIN whost
    - Checkout the latest code on all appservers
    - Remove all pyc files from app servers
    - Bounce celeryd, memcached , test services
    - Reload app code (touch wsgi file)

    Until we implement the checking out code to an isolated dir
    any failure on these steps need to be fixed or will result in
    breakage
    """
    execute(update_code, branch=branch, integration_branch=integration_branch)
    if skip_media == False:
        execute(update_static_media)
    if skip_celery == False:
        execute(bounce_celery)
    execute(bounce_memcached)
    execute(reload_app_servers)
    _notify("Amara {0} deployment".format(env.environment), "Deployed by {0} to {1} at {2} UTC".format(env.user, env.environment, datetime.utcnow()), env.notification_email)

@task
@runs_once
def update_static_media(compilation_level='ADVANCED_OPTIMIZATIONS', skip_compile=False, skip_s3=False):
    """
    Compiles and uploads static media to S3

    :param compilation_level: Level of optimization (default: ADVANCED_OPTIMIZATIONS)
    :param skip_s3: Skip upload to S3 (default: False)

    """
    env.host_string = env.builder_host
    if env.environment == 'demo':
        env.host_string = env.demo_hosts.get('app')
        root_dir = '/var/tmp/{0}'.format(env.revision)
        build_dir = '{0}/unisubs'.format(root_dir)
        ve_dir = '{0}/ve'.format(root_dir)
        integration_dir = '{0}/unisubs-integration'.format(build_dir)
        python_exe = '{0}/bin/python'.format(ve_dir)
    else:
        ve_dir = '{0}/{1}/unisubs'.format(env.build_ve_root, env.environment)
        build_dir = '{0}/{1}/unisubs'.format(env.build_apps_root, env.environment)
        integration_dir = '{0}/unisubs-integration'.format(build_dir)
        python_exe = '{0}/bin/python'.format(ve_dir)
    _reset_permissions(build_dir)
    _reset_permissions(env.build_ve_root)
    # update repositories
    with Output("Updating the main unisubs repo"), cd(build_dir):
        _git_pull()
        _switch_branch(env.revision, app_dir=build_dir)
    with Output("Updating the integration repo"), cd(integration_dir):
        _git_checkout_branch_and_reset(
            _get_optional_repo_version(build_dir, 'unisubs-integration'),
            branch=None,
            run_as_sudo=True
        )
    # must be ran before we compile anything
    with Output("Updating commit"), cd(build_dir):
        run('python deploy/create_commit_file.py')
        run('cat commit.py')
    # virtualenv
    with Output("Updating virtualenv"):
        with settings(warn_only=True):
            run('virtualenv --distribute -q {0}'.format(ve_dir))
        with cd('{0}/deploy'.format(build_dir)):
            run('yes i | {0}/bin/pip install -r requirements.txt'.format(ve_dir), pty=True)
    if skip_compile == False:
        with Output("Compiling media"), cd(build_dir), settings(warn_only=True):
            run('{0} manage.py  compile_media --compilation-level={1} --settings=unisubs_settings'.format(python_exe, compilation_level))
    if env.s3_bucket and skip_s3 == False:
        with Output("Uploading to S3"), cd(build_dir):
            run('{0} manage.py  send_to_s3 --settings=unisubs_settings'.format(python_exe))
    # temporary fix for dev until better dev compile solution
    # this also assumes the "builder" host is the same as dev (app-00-dev)
    if env.environment == 'dev':
        with cd(build_dir):
            sudo('cp -rf media/static-cache {0}/media/'.format(env.app_dir))

@task
@runs_once
@roles('data')
def update_django_admin_media():
    """
    Uploads Django Admin static media to S3

    """
    with Output("Uploading Django admin media"):
        media_dir = '{0}/lib/python2.6/site-packages/django/contrib/admin/static/media/'.format(env.ve_dir)
        s3_bucket = 's3.{0}.amara.org/admin/'.format(env.environment)
        sudo('s3cmd -P -c /etc/s3cfg sync {0} s3://{1}'.format(media_dir, s3_bucket))

@task
@roles('app')
def update_django_admin_media_dev():
    """
    Uploads Django Admin static media for dev

    This is separate from the update_django_admin_media task as this needs to
    run on each webserver for the dev environment.

    """
    with Output("Copying Django Admin static media"), cd(env.app_dir):
        media_dir = '{0}/lib/python2.6/site-packages/django/contrib/admin/media/'.format(env.ve_dir)
        # copy media to local dir
        run('cp -r {0} ./media/admin'.format(media_dir))

def _switch_branch(branch, app_dir=None):
    if not app_dir:
        app_dir = env.app_dir
    with cd(app_dir), settings(warn_only=True):
        run('git fetch')
        run('git branch --track {0} origin/{0}'.format(branch))
        run('git checkout {0}'.format(branch))
        _git_pull()
@task
@roles('app', 'data')
def switch_branch(branch):
    """
    Switches the current branch

    :param branch: Name of branch to switch

    """
    with Output('Switching to {0}'.format(branch)):
        _switch_branch(branch)

def _get_amara_config():
    old_host = env.host_string
    env.host_string = env.dev_host
    conf = None
    with hide('running', 'stdout'):
        conf = sudo('cat /etc/amara_config.json')
    try:
        conf = json.loads(conf)
    except:
        raise RuntimeError('Unable to parse Amara config')
    env.host_string = old_host
    return conf

def _create_nginx_instance(name=None, url_prefix=None):
    """
    Creates an Nginx instance (for demos)

    :param name: Name of instance
    :param url_prefix: URL prefix (default: name)

    """
    env.host_string = env.demo_hosts.get('app')
    if not url_prefix:
        url_prefix = name
    # nginx config
    run('cp /etc/nginx/conf.d/amara_dev.conf /tmp/{0}.conf'.format(name))
    run("sed -i 's/server_name.*;/server_name {0}.demo.amara.org;/g' /tmp/{1}.conf".format(\
        url_prefix, name))
    run("sed -i 's/root \/opt\/apps\/dev/root \/var\/tmp\/{0}/g' /tmp/{0}.conf".format(\
        name))
    run("sed -i 's/root \/opt\/ve\/dev\/unisubs/root \/var\/tmp\/{0}\/ve/g' /tmp/{0}.conf".format(\
        name))
    run("sed -i 's/uwsgi_pass.*;/uwsgi_pass unix:\/\/\/tmp\/uwsgi_{0}.sock;/g' /tmp/{0}.conf".format(\
        name))
    sudo("mv /tmp/{0}.conf /etc/nginx/conf.d/{0}.conf".format(name))

def _remove_nginx_instance(name=None):
    """
    Removes an Nginx instance (for demos)

    :param name: Name of instance

    """
    env.host_string = env.demo_hosts.get('app')
    sudo('rm -f /etc/nginx/conf.d/{0}.conf'.format(name))
    sudo('rm -f /etc/init/uwsgi.unisubs.demo.{0}.conf'.format(name))

@parallel
def _clone_repo_demo(revision='dev', integration_revision=None,
    instance_name=None, service_password=None):
    run('git clone https://github.com/pculture/unisubs.git /var/tmp/{0}/unisubs'.format(\
        instance_name))
    with cd('/var/tmp/{0}/unisubs'.format(instance_name)):
        run('git checkout --force {0}'.format(revision))
    sudo('git clone git@github.com:pculture/unisubs-integration.git /var/tmp/{0}/unisubs/unisubs-integration'.format(instance_name))
    if not integration_revision:
        integration_revision = _get_optional_repo_version(env.app_dir, 'unisubs-integration')
    with cd('/var/tmp/{0}/unisubs/unisubs-integration'.format(instance_name)):
        sudo('git checkout --force {0}'.format(integration_revision))
    # build virtualenv
    run('virtualenv /var/tmp/{0}/ve'.format(instance_name))
    # install requirements
    with cd('/var/tmp/{0}/unisubs/deploy'.format(instance_name)):
        run('yes i | /var/tmp/{0}/ve/bin/pip install -r requirements.txt'.format(instance_name), pty=True)
    _reset_permissions('/var/tmp/{0}'.format(instance_name))

@parallel
def _configure_demo_app_settings(name=None, revision=None, service_password=None, \
    url_prefix=None):
    """
    Configures application settings (for demos)

    :param name: Instance name
    :param revision: Application revision
    :param service_password: Demo instance service password
    :param url_prefix: Instance url prefix

    """
    if not url_prefix:
        url_prefix = revision
    # private config
    private_conf = '/var/tmp/{0}/unisubs/server_local_settings.py'.format(name)
    run('cp /opt/apps/dev/unisubs/server_local_settings.py {0}'.format(private_conf))
    run("sed -i 's/^INSTALLATION.*/INSTALLATION = DEMO/g' {0}".format(
        private_conf))
    run("sed -i 's/MEDIA_URL.*/MEDIA_URL = \"http:\/\/{0}.demo.amara.org\/user-data\/\"/g' {1}".format(
        url_prefix, private_conf))
    run("sed -i 's/STATIC_URL.*/STATIC_URL = \"http:\/\/{0}.demo.amara.org\/site_media\/\"/g' {1}".format(
        url_prefix, private_conf))
    run("sed -i 's/BROKER_USER.*/BROKER_USER = \"{0}\"/g' {1}".format(
        name, private_conf))
    run("sed -i 's/BROKER_VHOST.*/BROKER_VHOST = \"\/{0}\"/g' {1}".format(
        name, private_conf))
    run("sed -i 's/BROKER_PASSWORD.*/BROKER_PASSWORD = \"{0}\"/g' {1}".format(
        service_password, private_conf))
    run("sed -i 's/DATABASE_NAME.*/DATABASE_NAME = \"{0}\"/g' {1}".format(
        name, private_conf))
    run("sed -i 's/DATABASE_USER.*/DATABASE_USER = \"{0}\"/g' {1}".format(
        name, private_conf))
    run("sed -i 's/DATABASE_PASSWORD.*/DATABASE_PASSWORD = \"{0}\"/g' {1}".format(
        service_password, private_conf))
    run("sed -i 's/HAYSTACK_SOLR_URL.*/HAYSTACK_SOLR_URL = \"http:\/\/{0}:8983\/solr\/{1}\"/g' {2}".format(env.demo_hosts.get('data'),
        name, private_conf))

def _configure_demo_app(name=None, revision=None, url_prefix=None):
    """
    Configures demo app (Django site, etc.)

    :param name: Application instance name
    :param revision: Application revision
    :param url_prefix: Application instance URL prefix

    """
    if not url_prefix:
        url_prefix = revision
    env.host_string = env.demo_hosts.get('app')
    private_conf = '/var/tmp/{0}/unisubs/server_local_settings.py'.format(revision)
    app_dir = '/var/tmp/{0}/unisubs'.format(name)
    ve_dir = '/var/tmp/{0}/ve'.format(name)
    python_exe = '{0}/bin/python'.format(ve_dir)
    with cd(app_dir):
        run('{0} deploy/create_commit_file.py'.format(python_exe))
    app_shell = '{0} manage.py shell --settings=unisubs_settings'.format(
        python_exe)
    django_site_cmd = 'from django.contrib.sites.models import Site ;' \
        'Site.objects.create(domain="{0}.{1}", name="{0}").id'.format(
        url_prefix, env.demo_domain)
    site_id = None
    with cd(app_dir):
        # this is horrible scraping to get the new site id
        # someone please make this better
        out = run('echo \'{0}\' | {1}'.format(django_site_cmd, app_shell))
        site_id = out.splitlines()[-3].split('>>>')[-1].strip().strip('L')
    run("sed -i 's/SITE_ID.*/SITE_ID = {0}/g' {1}".format(
        site_id, private_conf))

def _create_rabbitmq_instance(name=None, password=None):
    """
    Creates a RabbitMQ instance (for test envs)

    :param name: RabbitMQ vhost name
    :param password: Instance password (username is name)

    """
    env.host_string = env.demo_hosts.get('data')
    with settings(warn_only=True):
        sudo('rabbitmqctl add_vhost /{0}'.format(name))
        sudo('rabbitmqctl add_user {0} {1}'.format(name, password))
        sudo('rabbitmqctl set_permissions -p /{0} {0} ".*" ".*" ".*"'.format(name))

def _remove_rabbitmq_instance(name=None):
    """
    Removes a RabbitMQ instance (for test envs)

    :param name: RabbitMQ vhost name

    """
    env.host_string = env.demo_hosts.get('data')
    with settings(warn_only=True):
        sudo('rabbitmqctl delete_user {0}'.format(name))
        sudo('rabbitmqctl delete_vhost /{0}'.format(name))

def _create_celery_instance(name=None):
    """
    Creates a Celery worker instance

    :param name: Celery instance name

    """
    env.host_string = env.demo_hosts.get('data')
    celeryd_tmpl = """
description "unisubs: celeryd ({0})"
start on runlevel [2345]
stop on runlevel [06]

exec /var/tmp/{0}/ve/bin/python /var/tmp/{0}/unisubs/manage.py celeryd -B -c 4 \
-E -f /var/tmp/{0}/celeryd.log --settings unisubs_settings
""".format(name)
    celerycam_tmpl = """
description "unisubs: celerycam ({0})"
start on runlevel [2345]
stop on runlevel [06]

exec /var/tmp/{0}/ve/bin/python /var/tmp/{0}/unisubs/manage.py celerycam \
-f /var/tmp/{0}/celerycam.log --settings unisubs_settings
""".format(name)
    with settings(warn_only=True):
        with open('.temp-celeryd', 'w') as f:
            f.write(celeryd_tmpl)
        put('.temp-celeryd', '/etc/init/celeryd.{0}.conf'.format(name),
            use_sudo=True)
        with open('.temp-celerycam', 'w') as f:
            f.write(celerycam_tmpl)
        put('.temp-celerycam', '/etc/init/celerycam.{0}.conf'.format(name),
            use_sudo=True)
        os.remove('.temp-celeryd')
        os.remove('.temp-celerycam')
    sudo('service celeryd.{0} start'.format(name))
    sudo('service celerycam.{0} start'.format(name))

def _remove_celery_instance(name=None):
    """
    Removes a Celery instance

    :param name: Celery instance name

    """
    env.host_string = env.demo_hosts.get('data')
    with settings(warn_only=True):
        sudo('service celeryd.{0} stop'.format(name))
        sudo('service celerycam.{0} stop'.format(name))
        sudo('rm -f /etc/init/celeryd.{0}.conf'.format(name))
        sudo('rm -f /etc/init/celerycam.{0}.conf'.format(name))

def _create_rds_instance(name=None, password=None, copy_production_data=False):
    """
    Creates an RDS instance (on dev RDS host)

    :param name: RDS DB name (also used for username)
    :param password: RDS user password
    :param copy_production_data: Copy production data into demo env

    """
    env.host_string = env.demo_hosts.get('app')
    with hide('running', 'stdout', 'warnings'):
        conf = _get_amara_config()
        env_cfg = conf.get('rds').get('environments').get('dev')
        rds_user = env_cfg.get('user')
        rds_host = env_cfg.get('host')
        rds_password = env_cfg.get('password')
        sql_cmd = 'mysql -u{0} -p{1} -h{2}'.format(rds_user, rds_password,
            rds_host)
        run('echo "create user {0}@\'%\' identified by \'{1}\';" | {2}'.format(
            name, password, sql_cmd))
        run('echo "create database {0};" | {1}'.format(
            name, sql_cmd))
        # can't grant all as RDS doesn't allow it
        run('echo "grant select,insert,update,delete,create,index,alter,'\
            'create temporary tables,lock tables,execute,create view,show view,'\
            'create routine, alter routine on {0}.* to {0}@\'%\';" | {1}'.format(
            name, sql_cmd))
    with hide('running'):
        # copy existing data if needed
        if copy_production_data:
            print('Copying production data')
            prod_cfg = conf.get('rds').get('environments').get('production')
            prod_rds_user = prod_cfg.get('user')
            prod_rds_host = prod_cfg.get('host')
            prod_rds_password = prod_cfg.get('password')
            prod_rds_db_name = prod_cfg.get('name')
            dump_cmd = 'mysqldump -u{0} -p{1} -h{2} -n --add-drop-database=FALSE --add-drop-table=FALSE --single-transaction {3} > /tmp/{4}.sql'.format(
                prod_rds_user, prod_rds_password, prod_rds_host, prod_rds_db_name,
                name)
            load_cmd = 'mysql -u{0} -p{1} -h{2} {3} < /tmp/{3}.sql ; rm -rf /tmp/{3}.sql'.format(
                rds_user, rds_password, rds_host, name)
            sudo(dump_cmd)
            sudo(load_cmd)

def _remove_rds_instance(name=None):
    """
    Notifies for RDS instance removal

    :param name: RDS instance name

    """
    msg = "Notification for RDS instance {0} removal by {1}".format(name,
        env.user)
    _notify('RDS Instance Removal', msg, env.notification_email)

@task
def _run_puppet_agent():
    with settings(warn_only=True), hide('running', 'stdout', 'warnings'):
        print('Waiting for current Puppet agent to stop...')
        while True:
            res = sudo('puppet agent -t --server puppet.amara.org')
            if res.return_code != 1:
                break
            time.sleep(10)

def _create_solr_instance(name=None):
    """
    Creates a Solr instance (for demos)

    :param name: Solr core name

    """
    env.host_string = env.demo_hosts.get('data')
    solr_cfg = '/etc/solr_extra_cores.json'
    try:
        solr_config = run('cat {0}'.format(solr_cfg))
        solr_extra_cores = json.loads(solr_config)
    except:
        raise RuntimeError('Unable to parse extra solr core config')
    if name not in solr_extra_cores:
        solr_extra_cores.append(name)
    with open('.temp-solr', 'w') as f:
        f.write(json.dumps(solr_extra_cores))
    put('.temp-solr', '{0}'.format(solr_cfg),
        use_sudo=True)
    os.remove('.temp-solr')
    # run puppet to create core
    _run_puppet_agent()
    # update schema
    _update_solr_schema()

def _remove_solr_instance(name=None):
    """
    Removes Solr instance (for demos)

    :param name: Solr core name

    """
    env.host_string = env.demo_hosts.get('data')
    solr_cfg = '/etc/solr_extra_cores.json'
    try:
        solr_config = run('cat {0}'.format(solr_cfg))
        solr_extra_cores = json.loads(solr_config)
    except:
        raise RuntimeError('Unable to parse extra solr core config')
    if name in solr_extra_cores:
        solr_extra_cores.remove(name)
    with open('.temp-solr', 'w') as f:
        f.write(json.dumps(solr_extra_cores))
    put('.temp-solr', '{0}'.format(solr_cfg),
        use_sudo=True)
    os.remove('.temp-solr')
    sudo('rm -rf /etc/solr/conf/{0}'.format(name))
    # run puppet to remove core
    _run_puppet_agent()
    sudo('service tomcat6 restart')

def _create_jenkins_job(name=None, revision=None):
    """
    Creates a Jenkins job

    :param name: Name of job
    :param revision: Amara revision

    """
    env.host_string = env.jenkins_host
    jenkins_config = '{0}/{1}/config.xml'.format(env.jenkins_jobs_dir, name)
    sudo('cp -rf {0}/unisubs-staging {0}/{1}'.format(env.jenkins_jobs_dir, name))
    sudo("sed -i 's/<name>staging<\/name>/<name>{0}<\/name>/g' {1}".format(revision,
        jenkins_config))
    sudo("service jenkins restart")

def _remove_jenkins_job(name=None):
    """
    Removes a Jenkins job

    :param name: Job name

    """
    env.host_string = env.jenkins_host
    sudo('rm -rf {0}/{1}'.format(env.jenkins_jobs_dir, name))
    sudo('service jenkins restart')

def _configure_demo_db(name=None):
    """
    Syncs demo database

    :param name: Application instance name

    """
    env.host_string = env.demo_hosts.get('app')
    app_dir = '/var/tmp/{0}/unisubs'.format(name)
    ve_dir = '/var/tmp/{0}/ve'.format(name)
    python_exe = '{0}/bin/python'.format(ve_dir)
    with cd(app_dir):
        run('{0} manage.py syncdb --all --noinput --settings=unisubs_settings'.format(
        python_exe))
        run('{0} manage.py migrate --fake --settings=unisubs_settings'.format(
        python_exe))

def _create_instance_name(name):
    return name.replace('-', '_')[:8]

@task
@parallel
def create_demo(integration_revision=None, skip_media=False, url_prefix=None,
    copy_production_data=False):
    """
    Deploys the specified revision for live testing

    :param integration_revision: Integrations revision to test
    :param skip_media: Skip media compilation (default: False)
    :param url_prefix: URL prefix for instance (i.e.: mybranch - default: revision or branch)
    :param copy_production_data: Copy existing production data and load into demo (warning: takes a long time)

    """
    env.hosts = env.demo_hosts.values()
    revision = env.revision
    instance_name = _create_instance_name(env.revision)
    service_password = ''.join(random.Random().sample(string.letters+string.digits, 8))
    if not url_prefix:
        url_prefix = revision
    with Output("Creating app directories"):
        for k,v in env.demo_hosts.iteritems():
            env.host_string = v
            run('mkdir -p /var/tmp/{0}'.format(instance_name))
    with Output("Configuring Nginx"):
        _create_nginx_instance(name=instance_name, url_prefix=url_prefix)
    with Output("Configuring uWSGI"):
        # uwsgi ini
        run('cp /etc/uwsgi.unisubs.dev.ini /tmp/uwsgi.unisubs.{0}.ini'.format(instance_name))
        run("sed -i 's/socket.*/socket = \/tmp\/uwsgi_{0}.sock/g' /tmp/uwsgi.unisubs.{0}.ini".format(\
            instance_name))
        run("sed -i 's/virtualenv.*/virtualenv = \/var\/tmp\/{0}\/ve/g' /tmp/uwsgi.unisubs.{0}.ini".format(\
            instance_name))
        run("sed -i 's/wsgi-file.*/wsgi-file = \/var\/tmp\/{0}\/unisubs\/deploy\/unisubs.wsgi/g' /tmp/uwsgi.unisubs.{0}.ini".format(\
            instance_name))
        run("sed -i 's/log-syslog.*/log-syslog = uwsgi.unisubs.{0}/g' /tmp/uwsgi.unisubs.{0}.ini".format(\
            instance_name))
        run("sed -i 's/touch-reload.*/touch-reload = \/var\/tmp\/{0}\/unisubs\/deploy\/unisubs.wsgi/g' /tmp/uwsgi.unisubs.{0}.ini".format(\
            instance_name))
        run("sed -i 's/pythonpath.*/pythonpath = \/var\/tmp\/{0}/g' /tmp/uwsgi.unisubs.{0}.ini".format(\
            instance_name))
        # uwsgi upstart
    with Output("Configuring upstart"):
        run('cp /etc/init/uwsgi.unisubs.dev.conf /tmp/uwsgi.unisubs.{0}.conf'.format(instance_name))
        run("sed -i 's/exec.*/exec uwsgi --ini \/var\/tmp\/{0}\/uwsgi.unisubs.{0}.ini/g' /tmp/uwsgi.unisubs.{0}.conf".format(instance_name))
        sudo("mv /tmp/uwsgi.unisubs.{0}.conf /etc/init/uwsgi.unisubs.demo.{0}.conf".format(instance_name))
        run('mv /tmp/uwsgi.unisubs.{0}.ini /var/tmp/{0}/uwsgi.unisubs.{0}.ini'.format(instance_name))
    # RDS DB instance
    with Output("Configuring RDS"), settings(warn_only=True):
        _create_rds_instance(name=instance_name, password=service_password,
            copy_production_data=copy_production_data)
    # clone code
    with Output("Cloning and building environments"), settings(warn_only=True):
        env.hosts = env.demo_hosts.values()
        execute(_clone_repo_demo, revision=revision,
            integration_revision=integration_revision,
            instance_name=instance_name, service_password=service_password)
    with Output("Configuring application settings"):
        env.host_string = env.demo_hosts.get('app')
        env.hosts = env.demo_hosts.values()
        execute(_configure_demo_app_settings, instance_name, revision, service_password,
            url_prefix)
    if not copy_production_data:
        # DB sync
        with Output("Syncing and migrating database"):
            env.host_string = env.demo_hosts.get('app')
            _configure_demo_db(name=instance_name)
    # Django site with <revision>.demo.amara.org url
    with Output("Configuring demo settings"):
        env.host_string = env.demo_hosts.get('app')
        _configure_demo_app(instance_name, revision, url_prefix)
    # celery
    with Output("Configuring Celery"), settings(warn_only=True):
        _create_celery_instance(name=instance_name)
    # rabbitmq
    with Output("Configuring RabbitMQ"), settings(warn_only=True):
        _create_rabbitmq_instance(name=instance_name, password=service_password)
    # solr instance
    with Output("Configuring Solr"):
        _create_solr_instance(name=instance_name)
    # jenkins instance
    with Output("Configuring Jenkins"):
        _create_jenkins_job(name=instance_name, revision=revision)
    # compile media
    if not skip_media:
        with Output("Compiling static media"):
            env.host_string = env.demo_hosts.get('app')
            # create a symlink to google closure library for compilation
            sudo('ln -sf /opt/google-closure /var/tmp/{0}/unisubs/media/js/closure-library'.format(instance_name))
            with cd('/var/tmp/{0}/unisubs'.format(instance_name)), settings(warn_only=True):
                python_exe = '/var/tmp/{0}/ve/bin/python'.format(instance_name)
                run('{0} deploy/create_commit_file.py'.format(python_exe))
                run('{0} manage.py  compile_media --compilation-level={1} --settings=unisubs_settings'.format(python_exe, 'ADVANCED_OPTIMIZATIONS'))
    with Output("Starting {0} demo".format(revision)):
        env.host_string = env.demo_hosts.get('app')
        sudo('service nginx reload')
        sudo('service uwsgi.unisubs.demo.{0} start'.format(instance_name))
    print('\nDemo should be available at http://{0}.demo.amara.org'.format(url_prefix))

@task
def remove_demo():
    """
    Removes live testing demo

    :param revision: Revision that was used in launching the demo

    """
    revision = env.revision
    instance_name = _create_instance_name(env.revision)
    # remove demo
    with Output("Stopping uWSGI"):
        env.host_string = env.demo_hosts.get('app')
        with settings(warn_only=True):
            sudo('service uwsgi.unisubs.demo.{0} stop'.format(instance_name))
    with Output("Removing Celery instance"):
        _remove_celery_instance(instance_name)
    with Output("Removing RabbitMQ instance"):
        _remove_rabbitmq_instance(instance_name)
    with Output("Removing RDS instance"):
        _remove_rds_instance(instance_name)
    with Output("Removing Solr instance"):
        _remove_solr_instance(instance_name)
    with Output("Removing nginx config"):
        _remove_nginx_instance(instance_name)
    with Output("Removing Jenkins job"):
        _remove_jenkins_job(instance_name)
    with Output("Restarting nginx"):
        env.host_string = env.demo_hosts.get('app')
        sudo('service nginx reload')
    with Output("Removing app directories for {0}".format(revision)):
        for k,v in env.demo_hosts.iteritems():
            env.host_string = v
            sudo('rm -rf /var/tmp/{0}'.format(instance_name))

@task
def show_demos():
    """
    Shows currently deployed demos

    """
    env.host_string = env.demo_hosts.get('app')
    envs = []
    with Output("Getting current deployed demo environment"):
        with settings(warn_only=True), hide('warnings', 'running'), cd('/var/tmp'):
            envs = run('find . -maxdepth 2 -type d -name unisubs').splitlines()
    if envs:
        print("\nEnvironments:")
        # get demo info
        for demo_env in envs:
            rev = demo_env.split('/')[1]
            # get deployed url - this is UGLY
            with hide('warnings', 'running', 'stdout'):
                url = run('cat /etc/nginx/conf.d/{0}.conf | grep server_name'.format(
                    rev)).split('server_name')[-1].strip().replace(';', '')
            print('Revision {0}: http://{1}'.format(rev, url))
    else:
        print('\nThere are no deployed demo environments.')

@task
def configure_scaling_instances(skip_puppet=False):
    """
    Configures instances upon scaling

    """
    hostname = 'app-scaling-{0}'.format(env.environment)
    with Output("Updating hostname"), hide('running', 'stdout'):
        sudo('echo "{0}.amara.org" > /etc/hostname'.format(hostname))
        sudo("sed -i 's/127.0.0.1.*/127.0.0.1 localhost {0} {0}.amara.org/g' /etc/hosts".format(
            hostname))
        sudo('/etc/init.d/hostname restart')
    if skip_puppet == False:
        _run_puppet_agent()
    _update_code()
    _update_virtualenv()
    with Output("Restarting uWSGI"):
        sudo('service uwsgi.unisubs.{0} restart'.format(env.environment))
        with settings(warn_only=True), hide('running', 'stdout'):
            run('wget -q -T 60 --delete-after http://{0}/en/'.format(env.host_string))

def _wait_for_instance_ready(instance=None):
    while True:
        instance.update()
        if instance.state == 'running':
            env.host_string = instance.public_dns_name
            # make sure ssh is ready
            try:
                run('uptime')
                break
            except:
                pass
        time.sleep(1)

def _update_lb_config(config):
    """
    Updates the current environment load balancer config

    :param config: Config as text

    """
    sudo('echo \'{0}\' > {1}'.format(config, env.lb_config))
    sudo('/etc/init.d/nginx reload')

def _add_nodes_to_lb(hosts=[]):
    """
    Adds specified nodes to current environment load balancer

    :param hosts: Host names to add (can be single host or list of hosts - as strings)

    """
    env.host_string = env.lb_host
    if not isinstance(hosts, list):
        hosts = [hosts]
    # get existing lb config
    with hide('running', 'stdout'):
        nginx_cfg = run('cat {0}'.format(env.lb_config)).splitlines()
    # insert new hosts
    for host in hosts:
        nginx_cfg.insert(1, '    server {0};'.format(host))
    _update_lb_config('\n'.join(nginx_cfg))

def _remove_nodes_from_lb(hosts=[]):
    """
    Removes specified hosts from current environment load balancer

    :param hosts: Host names to add (can be single host or list of hosts - as strings)

    """
    env.host_string = env.lb_host
    if not isinstance(hosts, list):
        hosts = [hosts]
    # get existing lb config
    with hide('running', 'stdout'):
        nginx_cfg = run('cat {0}'.format(env.lb_config)).splitlines()
    for host in hosts:
        [nginx_cfg.remove(x) for x in nginx_cfg if x.find(host) > -1]
    _update_lb_config('\n'.join(nginx_cfg))

def _configure_scaling_lb(hosts=[], action=None, scaling_instances=None):
    if not env.lb_host or not action: return
    action = action.lower()
    with Output("Configuring load balancer"):
        if action == 'up':
            # stop cron to prevent puppet from restoring config
            env.host_string = env.lb_host
            sudo('/etc/init.d/cron stop')
            # kill running puppet agents to prevent the edge case where
            # the config would be updated during a puppet run and then be
            # reverted back by puppet
            with settings(warn_only=True), hide('running', 'stdout', 'warnings'):
                sudo('killall puppet')
            # add nodes
            _add_nodes_to_lb(hosts)
        elif action == 'down':
            _remove_nodes_from_lb(hosts)
            if not scaling_instances:
                print('No remaining scaling instances ; enabling cron')
                # re-enable cron
                env.host_string = env.lb_host
                sudo('/etc/init.d/cron start')
        else:
            print('Invalid scaling action')

def _get_current_scaling_instances(ec2_conn, state=None):
    """
    Gets existing scaling instances for the current environment

    :param ec2_conn: Boto EC2 connection
    :param state: Current instance state to check (running, stopped)

    """
    # check for stopped instances
    all_res = ec2_conn.get_all_instances()
    scaling_instances = []
    for r in all_res:
        for i in r.instances:
            tags = i.__dict__.get('tags', {})
            if tags.has_key('scaling-instance') and \
                tags.get('scaling-env') == env.environment and \
                i.state == state:
                scaling_instances.append(i)
    return scaling_instances

@task
def scale(action='up', instances=1, skip_puppet=False, skip_lb=False):
    """
    Scales application server instances

    :param action: 'up' or 'down' for scaling direction
    :param instances: Number of instances to scale (default: 1)
    :param skip_puppet: Skip initial Puppet provisioning (default: False)
    :param skip_lb: Skip load balancer configuration (default: False)

    """
    import boto
    conf = _get_amara_config()
    instances = int(instances)
    env_cfg = conf.get('ec2')
    aws_id = env_cfg.get('user')
    aws_key = env_cfg.get('key')
    ec2_conn = boto.connect_ec2(aws_id, aws_key)
    action = action.lower()
    if action == 'up':
        state = 'stopped'
    else:
        state = 'running'
    scaling_instances = _get_current_scaling_instances(ec2_conn, state)
    if action == 'up':
        # disable known hosts in paramiko to prevent ssh hanging
        env.disable_known_hosts = True
        with Output("Scaling up by {0} instance(s)".format(instances)):
            print('Current available scaling instances: ' + str(scaling_instances))
            # check for existing scaling instances and slice if only needing a subset
            if scaling_instances:
                scaling_instances = scaling_instances[:instances]
            if len(scaling_instances) < instances:
                instance_count = int(instances) - len(scaling_instances)
                ami_id = env.app_server_ami_id
                instance_type = env.scaling_instance_type
                key_name = env.scaling_aws_key
                groups = env.scaling_security_groups
                res = ec2_conn.run_instances(ami_id, instance_type=instance_type,
                    min_count=instance_count, max_count=instance_count, key_name=key_name,
                    security_groups=groups)
                env.hosts = []
                for i in res.instances:
                    _wait_for_instance_ready(i)
                    # create tags
                    ec2_conn.create_tags([i.id], {
                        'scaling-instance': '1',
                        'scaling-env': env.environment,
                        'Name': 'pcf-amara-app-scaling-{0}'.format(env.environment)
                    })
                [scaling_instances.append for x in res.instances]
            for i in scaling_instances:
                if i.state != 'running':
                    i.start()
                    _wait_for_instance_ready(i)
        [env.hosts.append(x.public_dns_name) for x in scaling_instances]
        # configure instances
        execute(configure_scaling_instances, skip_puppet=skip_puppet)
        if skip_lb == False:
            # configure lb
            _configure_scaling_lb(hosts=env.hosts, action=action)
        _notify("Amara Scaling ({0})".format(env.environment),
            "Scaled {0} environment by {1} instance(s)".format(env.environment,
            instances), env.notification_email)
    elif action == 'down':
        if not scaling_instances: return
        with Output("Scaling down by {0} instance(s)".format(instances)):
            hosts = []
            stopped_instances = scaling_instances[:instances]
            print('Stopping instances: {0}'.format(', '.join([x.id
                for x in stopped_instances])))
            [hosts.append(i.public_dns_name) for i in stopped_instances]
            [i.stop() for i in stopped_instances]
        # get remaining instances
        remaining_instances = _get_current_scaling_instances(ec2_conn, state)
        if skip_lb == False:
            # configure lb
            _configure_scaling_lb(hosts=hosts, action=action,
                scaling_instances=remaining_instances)
        _notify("Amara Scaling ({0})".format(env.environment),
            "Request to terminate scaled instance(s) for {0} environment: {1}".format(env.environment, ','.join([i.id for i in stopped_instances])), env.notification_email)
    else:
        print('Invalid scaling action')
        return

@task
def run_new_relic(license=None):
    """
    Configures application servers for new relic for current environment

    :param license: New Relic license key

    """
    ve_dir = env.ve_dir
    # stop cron from restarting "normal" uwsgi
    with settings(warn_only=True):
        sudo('/etc/init.d/cron stop')
    sudo('{0}/bin/pip install newrelic'.format(ve_dir))
    with settings(warn_only=True):
        sudo('service uwsgi.unisubs.{0} stop'.format(env.environment))
    script = "export NEW_RELIC_APP_NAME=\'Amara ({2})\'\n"\
        "export NEW_RELIC_LICENSE_KEY={0}\n"\
        "{1}/bin/newrelic-admin run-program uwsgi "\
        "--pidfile /tmp/newrelic_uwsgi.pid "\
        "--ini /etc/uwsgi.unisubs.{2}.ini".format(license, ve_dir,
            env.environment)
    sudo('echo \"{0}\" > /tmp/run_newrelic.sh'.format(script))
    sudo('screen -d -m bash /tmp/run_newrelic.sh', pty=False)

@task
def stop_new_relic():
    """
    Stops the New Relic agent for the current environment

    """
    with settings(warn_only=True):
        sudo('killall -9 uwsgi')
        sudo('service uwsgi.unisubs.{0} start'.format(env.environment))
        # start cron
        sudo('/etc/init.d/cron start')

@task
@roles('app')
def enable_new_relic():
    """
    Enables the New Relic agent across environment application servers

    """
    conf = _get_amara_config()
    license = conf.get('newrelic', {}).get('license')
    with Output("Configuring and starting uWSGI with New Relic"):
        execute(run_new_relic, license)

@task
@roles('app')
def disable_new_relic():
    """
    Disables the New Relic agent and starts uWSGI

    """
    with Output("Disabling New Relic agent"):
        execute(stop_new_relic)

