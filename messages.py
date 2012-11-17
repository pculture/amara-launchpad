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
from flaskext.babel import gettext

ACCESS_DENIED = gettext('Access denied.')
CANNOT_DELETE_ADMIN = gettext('Cannot delete admin user.')
EMPTY_USERNAME_EMAIL = gettext('You must enter a username and email.')
ERROR_UPDATING_PASSWORD = gettext('There was an error updating your password.')
EXPIRED_INVALID_CODE = gettext('Invalid or expired code.')
HOST_ADDED = gettext('Host added.')
HOST_DELETED = gettext('Host deleted.')
INVALID_USERNAME = gettext('Invalid username')
INVALID_USERNAME_PASSWORD = gettext('Invalid username or password.')
LOGGED_OUT = gettext('You have been logged out.')
PASSWORDS_NOT_MATCH = gettext('Passwords do not match.')
PASSWORD_UPDATED = gettext('Password updated.  Please login.')
RESET_CODE_SENT = gettext('Please check your email.')
SSH_INFO_UPDATED = gettext('SSH info updated.')
USER_CREATED = gettext('User created.')
USER_DELETED = gettext('User deleted.')
