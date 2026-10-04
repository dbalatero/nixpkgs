import importlib.util
from pathlib import Path
import sqlite3
import unittest

spec = importlib.util.spec_from_file_location('cwa_oidc', Path(__file__).resolve().parents[1] / 'hosts/media/cwa_oidc.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OIDCTest(unittest.TestCase):
  def setUp(self):
    self.db = sqlite3.connect(':memory:')
    self.addCleanup(self.db.close)
    self.db.executescript('''
      CREATE TABLE oauthProvider (id INTEGER PRIMARY KEY, provider_name TEXT,
        active INTEGER, oauth_client_id TEXT, oauth_client_secret TEXT,
        oauth_base_url TEXT, oauth_authorize_url TEXT, oauth_token_url TEXT,
        oauth_userinfo_url TEXT, metadata_url TEXT, scope TEXT, username_mapper TEXT,
        email_mapper TEXT, login_button TEXT, oauth_admin_group TEXT);
      CREATE TABLE settings (config_login_type INTEGER, config_oauth_redirect_host TEXT,
        config_disable_standard_login INTEGER, config_enable_oauth_group_admin_management INTEGER,
        config_default_role INTEGER);
      INSERT INTO settings VALUES (0,'',0,1,0);
      CREATE TABLE user (name TEXT, role INTEGER, password TEXT);
      INSERT INTO user VALUES ('dbalatero',511,'existing-hash');
    ''')

  def apply(self, secret='test-secret'):
    with self.db:
      module.configure_oidc(self.db, secret=secret, auth_url='https://auth.netcat.cloud', public_url='https://books.netcat.cloud')

  def test_settings_and_existing_user_preserved(self):
    self.apply()
    self.assertEqual(self.db.execute('SELECT * FROM user').fetchall(), [('dbalatero',511,'existing-hash')])
    self.assertEqual(self.db.execute('SELECT * FROM settings').fetchone(), (2,'',0,0,258))
    self.assertEqual(self.db.execute('SELECT provider_name FROM oauthProvider WHERE active=1').fetchall(), [('generic',)])

  def test_reconcile_preserves_provider_identity_and_rotates_secret(self):
    self.apply()
    before = self.db.execute("SELECT id FROM oauthProvider WHERE provider_name='generic'").fetchone()
    self.apply("new-secret-with-'quote")
    self.assertEqual(self.db.execute('SELECT count(*) FROM oauthProvider').fetchone()[0], 3)
    self.assertEqual(self.db.execute("SELECT id FROM oauthProvider WHERE provider_name='generic'").fetchone(), before)
    self.assertEqual(self.db.execute("SELECT oauth_client_secret FROM oauthProvider WHERE provider_name='generic'").fetchone()[0], "new-secret-with-'quote")

  def test_reject_empty_secret(self):
    with self.assertRaises(ValueError):
      self.apply('')
    self.assertEqual(self.db.execute('SELECT count(*) FROM oauthProvider').fetchone()[0], 0)


if __name__ == '__main__':
  unittest.main()
