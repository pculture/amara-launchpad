# Amara Keymaker
Keymaker is a password reset application.  It will reset account passwords on
all hosts configured in the application.

# Setup

* mkvirtualenv keymaker
* pip install -r requirements.txt
* ./test_unit.sh -v (optional)
* Edit ADMIN_EMAIL in `config.py`
* python application.py

# Usage
To reset account passwords, enter your username and click the "Reset" button.
You will receive an email with a link.  Click the link and reset your password.

# Administration
If you have admin rights, you can login to the application and configure hosts,
SSH info, etc.  To login, visit `/admin`.

# ToDo
* Make password reset parallel
* Enable groups of servers to identify of which servers to change
