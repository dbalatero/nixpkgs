"""Apply Nix-owned request defaults before Seerr starts; keep secrets local."""
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def call(app, key, endpoint, body=None):
  request = urllib.request.Request(
    f"http://{app['hostname']}:{app['port']}/api/v3/{endpoint}",
    headers={"X-Api-Key": key, "Content-Type": "application/json"},
    data=None if body is None else json.dumps(body).encode())
  try:
    with urllib.request.urlopen(request, timeout=15) as response:
      return json.load(response)
  except urllib.error.HTTPError as error:
    raise RuntimeError(f"Servarr {endpoint}: HTTP {error.code}") from None


def configure(current, desired, credentials):
  current.setdefault('main', {}).update(
    applicationUrl=desired['applicationUrl'],
    defaultPermissions=desired['defaultPermissions'],
    mediaServerType=desired['mediaServerType'])
  current.setdefault('network', {})['trustProxy'] = True
  for name, app in desired['apps'].items():
    key = ET.parse(credentials / f'{name}.xml').getroot().findtext('ApiKey')
    if not key:
      raise RuntimeError(f'{name}: API key not initialized')
    profiles = [p for p in call(app, key, 'qualityprofile')
      if p['name'] == app['qualityProfile']]
    if len(profiles) != 1:
      raise RuntimeError(f'{name}: expected exactly one declared quality profile')
    if not any(root['path'] == app['root'] for root in call(app, key, 'rootfolder')):
      call(app, key, 'rootfolder', {'path': app['root']})
    servers = current.setdefault(name, [])
    matches = [s for s in servers if s.get('name') == name]
    if len(matches) > 1:
      raise RuntimeError(f'{name}: duplicate managed server')
    server = matches[0] if matches else {'id': max(
      (s['id'] for s in servers), default=-1) + 1}
    if not matches:
      servers.append(server)
    for other in servers:
      if not other.get('is4k', False):
        other['isDefault'] = False
    server.update(name=name, hostname=app['hostname'], port=app['port'],
      apiKey=key, useSsl=False, baseUrl='', is4k=False, isDefault=True,
      activeProfileId=profiles[0]['id'], activeProfileName=profiles[0]['name'],
      activeDirectory=app['root'], externalUrl=app['externalUrl'],
      syncEnabled=True, preventSearch=False, tags=[], tagRequests=False,
      overrideRule=[])
    if name == 'radarr':
      server['minimumAvailability'] = 'released'
    else:
      server.update(seriesType='standard', animeSeriesType='anime',
        activeAnimeProfileId=profiles[0]['id'], activeAnimeProfileName=profiles[0]['name'],
        activeAnimeDirectory=app['root'], animeTags=[],
        enableSeasonFolders=True, monitorNewItems='all')
  return current


def main():
  os.umask(0o077)
  desired = json.loads(Path(sys.argv[1]).read_text())
  path = Path(os.environ['CONFIG_DIRECTORY']) / 'settings.json'
  for attempt in range(12):
    try:
      current = json.loads(path.read_text()) if path.exists() else {}
      result = configure(current, desired, Path(os.environ['CREDENTIALS_DIRECTORY']))
      temporary = path.with_suffix('.json.tmp')
      temporary.write_text(json.dumps(result, indent=2) + '\n')
      temporary.chmod(0o600)
      temporary.replace(path)
      print('Seerr: movie and TV defaults configured; automatic search enabled')
      return
    except (OSError, RuntimeError, ET.ParseError) as error:
      if attempt == 11:
        raise SystemExit(f'Seerr configuration failed ({type(error).__name__})') from None
      time.sleep(5)


if __name__ == '__main__':
  main()
