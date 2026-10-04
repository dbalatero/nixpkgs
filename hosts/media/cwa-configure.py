"""Reconcile Nix-owned settings before CWA opens its listener."""
import os
from pathlib import Path
import sqlite3
import sys

from werkzeug.security import check_password_hash, generate_password_hash
from cwa_oidc import configure_oidc

password = Path('/run/secrets/cwa-admin-password').read_text().strip()
oidc_secret = Path('/run/secrets/cwa-oidc-secret').read_text().strip()
uid, gid = int(os.environ['PUID']), int(os.environ['PGID'])
# NAS mode skips upstream chown even for the local config directory. These
# files/parent directories are created by root but edited by the app.
for name in ('user_profiles.json', 'client_secrets.json', '.config',
    '.config/calibre', 'processed_books'):
  path = Path('/config') / name
  if path.exists():
    os.chown(path, uid, gid)
os.setgroups([gid])
os.setgid(gid)
os.setuid(uid)
sys.path.insert(0, '/app/calibre-web-automated/scripts')
from cwa_db import CWA_DB

cwa = CWA_DB()
with cwa.con:
  cwa.con.execute('''UPDATE cwa_settings SET
    default_settings=0, auto_convert=1, auto_convert_target_format='epub',
    auto_convert_ignored_formats='pdf', auto_ingest_ignored_formats='',
    auto_convert_retained_formats='azw3,mobi',
    auto_backup_imports=0, auto_backup_conversions=0, auto_backup_epub_fixes=0,
    kindle_epub_fixer=0
  ''')
cwa.con.close()

with sqlite3.connect('/config/app.db', timeout=30) as db:
  # Bootstrap once; subsequent starts preserve password changes made in the UI.
  marker = Path('/config/.nix-admin-initialized')
  if not marker.exists():
    existing = db.execute('SELECT id FROM user WHERE name=?', ('dbalatero',)).fetchone()
    if not existing:
      admin = db.execute('SELECT id,password FROM user WHERE name=?', ('admin',)).fetchone()
      if not admin or not check_password_hash(admin[1], 'admin123'):
        raise RuntimeError('Refusing to replace an existing administrator')
      db.execute('UPDATE user SET name=?,password=? WHERE id=?',
        ('dbalatero', generate_password_hash(password), admin[0]))
    db.commit()
    marker.touch(mode=0o600)
  db.execute('''UPDATE settings SET config_kobo_sync=1,
    config_calibre_web_title='Books', config_logfile='/dev/stdout',
    config_access_log=0, config_anonbrowse=0, config_public_reg=0
  ''')
  configure_oidc(db, secret=oidc_secret,
    auth_url=os.environ['NETCAT_AUTH_URL'], public_url=os.environ['NETCAT_BOOKS_URL'])
print('[nix-cwa] Library settings and administrator initialized')
