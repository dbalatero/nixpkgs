"""Preserve Plex account credentials while applying Nix-owned settings."""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def preferences(settings):
  folder = Path(settings['dataDir'])
  folder.mkdir(parents=True, exist_ok=True)
  path = folder / 'Preferences.xml'
  tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element('Preferences'))
  tree.getroot().attrib.update(settings['preferences'])
  temporary = path.with_suffix('.xml.tmp')
  tree.write(temporary, encoding='utf-8', xml_declaration=True)
  temporary.chmod(0o600)
  temporary.replace(path)


def libraries(settings):
  path = Path(settings['dataDir']) / 'Preferences.xml'
  token = ET.parse(path).getroot().get('PlexOnlineToken') if path.exists() else None
  if not token:
    return  # Waiting for the owner to claim the server, without log spam.
  def call(endpoint, method='GET', values=None):
    url = settings['url'] + endpoint
    if values:
      url += '?' + urllib.parse.urlencode(values)
    request = urllib.request.Request(url, method=method,
      headers={'X-Plex-Token': token, 'Accept': 'application/xml'})
    with urllib.request.urlopen(request, timeout=30) as response:
      data = response.read()
      return ET.fromstring(data) if data else None
  existing = call('/library/sections').findall('Directory')
  for library in settings['libraries']:
    matches = [entry for entry in existing if entry.get('title') == library['name']]
    if matches:
      if len(matches) != 1 or matches[0].get('type') != library['type']:
        raise RuntimeError('Existing library conflicts with declared library')
      if library['path'] not in [location.get('path') for location in matches[0].findall('Location')]:
        raise RuntimeError('Existing library has a different path; refusing to replace it')
      continue
    call('/library/sections', 'POST', {
      'name': library['name'], 'type': library['type'],
      'agent': library['agent'], 'scanner': library['scanner'],
      'location': library['path'], 'language': 'en-US'})
    print(f"Plex: created {library['name']} library", flush=True)


if __name__ == '__main__':
  os.umask(0o077)
  try:
    settings = json.loads(Path(sys.argv[1]).read_text())
    {'preferences': preferences, 'libraries': libraries}[sys.argv[2]](settings)
  except (OSError, RuntimeError, ET.ParseError) as error:
    raise SystemExit(f'Plex configuration failed ({type(error).__name__})') from None
