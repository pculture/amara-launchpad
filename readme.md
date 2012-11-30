# Amara Launchpad
Application for running Fabric workflows

# Setup (you must have Redis running)

* mkvirtualenv launchpad
* pip install -r requirements.txt
* (optional) edit config.py (or create local_config.py) with Redis connection info
* Create (or copy existing) fabfile.py to application directory
* python application.py

The first time the app is ran a user with username `admin` and password `launchpad`
will be created.
