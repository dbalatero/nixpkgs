import copy
import importlib.util
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


def load(name):
  path = Path(__file__).resolve().parents[1] / 'hosts/media' / f'{name}-configure.py'
  spec = importlib.util.spec_from_file_location(name, path)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


seerr = load('seerr')
plex = load('plex')


class FrontendTests(unittest.TestCase):
  def test_seerr_preserves_accounts_and_resolves_profile_ids(self):
    with tempfile.TemporaryDirectory() as folder:
      credentials = Path(folder)
      for name in ('radarr', 'sonarr'):
        (credentials / f'{name}.xml').write_text('<Config><ApiKey>test-key</ApiKey></Config>')
      desired = {'applicationUrl': 'https://download.example', 'defaultPermissions': 160, 'mediaServerType': 1,
        'apps': {name: {'hostname': '127.0.0.1', 'port': port,
          'qualityProfile': 'HD-1080p', 'root': root, 'externalUrl': 'https://' + name}
          for name, port, root in [('radarr', 7878, '/media/movies'), ('sonarr', 8989, '/media/tv')]}}
      current = {'main': {'apiKey': 'seerr-secret', 'mediaServerType': 1}, 'plex': {'machineId': 'server-id'},
        'public': {'initialized': True}, 'radarr': [{'id': 9, 'name': 'radarr'}]}
      roots = set()
      def call(app, key, endpoint, body=None):
        self.assertEqual(key, 'test-key')
        if endpoint == 'qualityprofile':
          return [{'id': 42, 'name': 'HD-1080p'}]
        if body:
          roots.add(body['path'])
          return body
        return [{'path': root} for root in roots]
      with patch.object(seerr, 'call', side_effect=call) as api:
        result = seerr.configure(copy.deepcopy(current), desired, credentials)
        repeated = seerr.configure(copy.deepcopy(result), desired, credentials)
      self.assertEqual(result, repeated)
      self.assertEqual(result['main']['apiKey'], 'seerr-secret')
      self.assertEqual(result['main']['mediaServerType'], 1)
      self.assertEqual(result['plex'], current['plex'])
      self.assertTrue(result['public']['initialized'])
      self.assertEqual(result['radarr'][0]['id'], 9)
      self.assertEqual(len(result['radarr']), 1)
      self.assertEqual(result['sonarr'][0]['activeProfileId'], 42)
      self.assertFalse(result['sonarr'][0]['preventSearch'])
      self.assertEqual(result['radarr'][0]['activeDirectory'], '/media/movies')
      self.assertEqual(len([c for c in api.call_args_list if len(c.args) == 4]), 2)

  def test_missing_profile_fails_before_root_creation(self):
    with tempfile.TemporaryDirectory() as folder:
      credentials = Path(folder)
      (credentials / 'radarr.xml').write_text('<Config><ApiKey>test</ApiKey></Config>')
      desired = {'applicationUrl': 'https://download.example', 'defaultPermissions': 160, 'mediaServerType': 1,
        'apps': {'radarr': {'qualityProfile': 'HD-1080p'}}}
      with patch.object(seerr, 'call', return_value=[]) as api:
        with self.assertRaisesRegex(RuntimeError, 'quality profile'):
          seerr.configure({}, desired, credentials)
      self.assertEqual(api.call_count, 1)

  def test_first_start_requires_owner_login(self):
    desired = {'applicationUrl': 'https://download.example', 'defaultPermissions': 160, 'apps': {}}
    for current in ({}, {'main': {'mediaServerType': 1}}):
      result = seerr.configure(current, desired, Path('/unused'), has_owner=False)
      self.assertEqual(result['main']['mediaServerType'], 4)
    result = seerr.configure({'main': {'mediaServerType': 1}}, desired, Path('/unused'), has_owner=True)
    self.assertEqual(result['main']['mediaServerType'], 1)

  def test_plex_preferences_preserve_claim(self):
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'Preferences.xml'
      path.write_text('<Preferences PlexOnlineToken="private-token" MachineIdentifier="id"/>')
      settings = {'dataDir': folder, 'preferences': {'LogNumFiles': '5', 'allowMediaDeletion': '0'}}
      plex.preferences(settings)
      plex.preferences(settings)
      observed = ET.parse(path).getroot().attrib
      self.assertEqual(observed['PlexOnlineToken'], 'private-token')
      self.assertEqual(observed['MachineIdentifier'], 'id')
      self.assertEqual(observed['LogNumFiles'], '5')
      self.assertEqual(path.stat().st_mode & 0o777, 0o600)

  def test_plex_waits_for_claim_without_network_calls(self):
    with tempfile.TemporaryDirectory() as folder:
      with patch.object(plex.urllib.request, 'urlopen') as request:
        plex.libraries({'dataDir': folder})
      request.assert_not_called()

  def test_plex_subtitles_updates_only_declared_account_preferences(self):
    with tempfile.TemporaryDirectory() as folder:
      (Path(folder) / 'Preferences.xml').write_text('<Preferences PlexOnlineToken="private"/>')
      profile = {'autoSelectAudio': False, 'defaultAudioLanguage': 'fr'}
      writes = []
      def request(req, timeout):
        self.assertEqual(req.get_header('X-plex-token'), 'private')
        if req.get_method() == 'PUT':
          self.assertEqual(req.full_url, 'https://plex.tv/api/v2/user/profile')
          values = json.loads(req.data)
          writes.append(values)
          profile.update(values)
          return io.BytesIO(b'')
        return io.BytesIO(json.dumps({'profile': profile}).encode())
      desired = {'autoSelectAudio': True, 'autoSelectSubtitle': 2, 'defaultSubtitleLanguage': 'en'}
      with patch.object(plex.urllib.request, 'urlopen', side_effect=request):
        plex.subtitles({'dataDir': folder, 'accountProfile': desired})
        plex.subtitles({'dataDir': folder, 'accountProfile': desired})
      self.assertEqual(writes, [desired])
      self.assertEqual(profile['defaultAudioLanguage'], 'fr')


if __name__ == '__main__':
  unittest.main()
