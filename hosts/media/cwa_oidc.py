"""Declare the CWA generic OIDC provider without changing existing users."""


def configure_oidc(db, *, secret, auth_url, public_url):
  if not secret or secret.strip() != secret:
    raise ValueError('OIDC client secret must be nonempty without surrounding whitespace')
  auth_url, public_url = auth_url.rstrip('/'), public_url.rstrip('/')
  if not auth_url.startswith('https://') or not public_url.startswith('https://'):
    raise ValueError('OIDC requires HTTPS endpoints')
  # CWA expects all three provider records even when only generic is enabled.
  for name in ('github', 'google', 'generic'):
    if not db.execute('SELECT 1 FROM oauthProvider WHERE provider_name=?', (name,)).fetchone():
      db.execute('INSERT INTO oauthProvider (provider_name,active) VALUES (?,0)', (name,))
  db.execute('''UPDATE oauthProvider SET active=1,
    oauth_client_id='netcat-books', oauth_client_secret=?,
    oauth_base_url=?, oauth_authorize_url=?, oauth_token_url=?, oauth_userinfo_url=?,
    metadata_url=?, scope='openid profile email', username_mapper='preferred_username',
    email_mapper='email', login_button='Authentik', oauth_admin_group=''
    WHERE provider_name='generic'
  ''', (secret, auth_url + '/application/o/books/',
    auth_url + '/application/o/authorize/', auth_url + '/application/o/token/',
    auth_url + '/application/o/userinfo/',
    auth_url + '/application/o/books/.well-known/openid-configuration'))
  # 258 = download (2), browser reader (256). Personal shelves need no role;
  # the separate edit-shelves bit grants editing of public shelves.
  # Preserve local login and manual admin grants, including dbalatero's role.
  # In CWA 4.0.8 redirect_host is incorrectly passed to Flask-Dance's
  # post-login redirect_url. Leave it empty; Caddy's forwarded headers produce
  # the HTTPS callback via url_for without redirecting back to the callback.
  db.execute('''UPDATE settings SET config_login_type=2,
    config_oauth_redirect_host='', config_disable_standard_login=0,
    config_enable_oauth_group_admin_management=0, config_default_role=258
  ''')
