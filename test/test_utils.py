import unittest
import utils
from utils import db, accounts
import config

class UtilsTestCase(unittest.TestCase):
    def setUp(self):
        self.test_user_username = 'testuser'
        self.test_user_email = 'test@test.com'
        self.test_user_password = 't35t'
        self.test_user_is_admin = False
        config.REDIS_DB = 14

    def tearDown(self):
        rds = utils.get_redis_connection()
        rds.flushdb()

    def _create_user(self):
        db.create_user(self.test_user_username, self.test_user_password,
            self.test_user_email, self.test_user_is_admin)
        user = db.get_user(self.test_user_username)
        return user

    def test_create_user(self):
        user = self._create_user()
        self.assertEqual(user.get('username'), self.test_user_username)
        self.assertEqual(user.get('email'), self.test_user_email)
        self.assertNotEqual(user.get('password'), self.test_user_password)
        self.assertEqual(user.get('password'),
            utils.hash_text(self.test_user_password))
        self.assertEqual(user.get('is_admin'), self.test_user_is_admin)

    def test_get_user(self):
        self._create_user()
        u = db.get_user(self.test_user_username)
        self.assertNotEqual(u, None)
        self.assertTrue(u.has_key('username'))
