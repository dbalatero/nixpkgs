"""Reconcile Nix-owned Bazarr settings without exposing runtime credentials."""
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import yaml


def configure(settings):
  path = Path(settings['dataDir']) / 'config/config.yaml'
  path.parent.mkdir(parents=True, exist_ok=True)
  config = yaml.safe_load(path.read_text()) if path.exists() else {}
  for section, values in settings['config'].items():
    config.setdefault(section, {}).update(values)
  general = config['general']
  general['enabled_providers'] = sorted(set(
    general.get('enabled_providers', []) + settings['providers'])
    - set(settings.get('disabledProviders', [])))
  for name, values in settings['apps'].items():
    key = ET.parse(Path(os.environ['CREDENTIALS_DIRECTORY']) / f'{name}.xml').findtext('ApiKey')
    if not key:
      raise RuntimeError(f'{name} API key is missing')
    config.setdefault(name, {}).update({
      'ip': '127.0.0.1', 'port': values['port'], 'ssl': False,
      'base_url': '/', 'apikey': key, 'only_monitored': False,
    })
  temporary = path.with_suffix('.yaml.tmp')
  temporary.write_text(yaml.safe_dump(config))
  temporary.chmod(0o600)
  temporary.replace(path)


def profiles(settings):
  config = yaml.safe_load((Path(settings['dataDir']) / 'config/config.yaml').read_text())
  key = config['auth']['apikey']

  def call(endpoint, values=None):
    data = urllib.parse.urlencode(values, doseq=True).encode() if values is not None else None
    request = urllib.request.Request(
      f"http://127.0.0.1:{settings['port']}/api/{endpoint}", data=data,
      headers={'X-API-KEY': key})
    with urllib.request.urlopen(request, timeout=120) as response:
      body = response.read()
      return json.loads(body) if body else None

  existing = call('system/languages/profiles')
  matching = [p for p in existing if p['name'] == settings['profile']['name']]
  if len(matching) > 1:
    raise RuntimeError('Multiple Nix English profiles exist')
  profile_id = matching[0]['profileId'] if matching else max(
    [p['profileId'] for p in existing], default=0) + 1
  desired = dict(settings['profile'], profileId=profile_id)
  values = {}
  if not matching or matching[0] != desired:
    values['languages-profiles'] = json.dumps(
      [p for p in existing if p['profileId'] != profile_id] + [desired])
  languages = call('system/languages')
  if not any(lang['code2'] == 'en' and lang['enabled'] for lang in languages):
    values['languages-enabled'] = sorted(set(
      [lang['code2'] for lang in languages if lang['enabled']] + ['en']))
  for kind in ('serie', 'movie'):
    for suffix, value in [('enabled', True), ('profile', profile_id)]:
      field = f'{kind}_default_{suffix}'
      if config['general'].get(field) != value:
        values[f'settings-general-{field}'] = json.dumps(value)
  if values:
    call('system/settings', values)
  for endpoint, id_field, parameter in (
    ('series', 'sonarrSeriesId', 'seriesid'),
    ('movies', 'radarrId', 'radarrid'),
  ):
    entries = call(endpoint)['data']
    ids = [entry[id_field] for entry in entries if entry.get('profileId') != profile_id]
    if ids:
      call(endpoint, {parameter: ids, 'profileid': [profile_id] * len(ids)})
      print(f'Bazarr: assigned English profile to {len(ids)} {endpoint}', flush=True)


if __name__ == '__main__':
  os.umask(0o077)
  try:
    settings = json.loads(Path(sys.argv[1]).read_text())
    {'config': configure, 'profiles': profiles}[sys.argv[2]](settings)
  except Exception as error:
    # HTTP errors can contain credentials in their request URLs.
    raise SystemExit(f'Bazarr configuration failed ({type(error).__name__})') from None
