import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import yaml


path = Path(__file__).resolve().parents[1] / 'hosts/media/bazarr-configure.py'
spec = importlib.util.spec_from_file_location('bazarr_configure', path)
bazarr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bazarr)


class BazarrTests(unittest.TestCase):
  def test_merge_preserves_credentials_and_is_idempotent(self):
    with tempfile.TemporaryDirectory() as folder:
      root = Path(folder)
      (root / 'config').mkdir()
      path = root / 'config/config.yaml'
      path.write_text(yaml.safe_dump({
        'auth': {'apikey': 'private'},
        'opensubtitlescom': {'password': 'private-password'},
        'general': {'enabled_providers': ['opensubtitlescom', 'gestdown', 'tvsubtitles']},
      }))
      (root / 'sonarr.xml').write_text('<Config><ApiKey>sonarr-secret</ApiKey></Config>')
      settings = {'dataDir': folder, 'apps': {'sonarr': {'port': 8989}},
        'providers': ['yifysubtitles'], 'disabledProviders': ['gestdown', 'tvsubtitles'],
        'config': {'general': {'use_embedded_subs': True}}}
      with patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': folder}):
        bazarr.configure(settings)
        first = path.read_text()
        bazarr.configure(settings)
      self.assertEqual(first, path.read_text())
      result = yaml.safe_load(first)
      self.assertEqual(result['auth']['apikey'], 'private')
      self.assertEqual(result['opensubtitlescom']['password'], 'private-password')
      self.assertEqual(result['general']['enabled_providers'], ['opensubtitlescom', 'yifysubtitles'])
      self.assertEqual(result['sonarr']['apikey'], 'sonarr-secret')
      self.assertEqual(path.stat().st_mode & 0o777, 0o600)

  def test_profiles_preserve_other_profiles_and_use_api_boolean_encoding(self):
    with tempfile.TemporaryDirectory() as folder:
      root = Path(folder)
      (root / 'config').mkdir()
      (root / 'config/config.yaml').write_text(yaml.safe_dump({
        'auth': {'apikey': 'private'}, 'general': {},
      }))
      existing = {'profileId': 7, 'name': 'Other language'}
      posts = {}
      def request(req, timeout):
        endpoint = req.full_url.split('/api/')[1]
        self.assertEqual(req.get_header('X-api-key'), 'private')
        if req.data is not None:
          posts[endpoint] = parse_qs(req.data.decode())
          return io.BytesIO(b'')
        responses = {
          'system/languages/profiles': [existing],
          'system/languages': [{'code2': 'fr', 'enabled': True}],
          'series': {'data': [{'sonarrSeriesId': 12, 'profileId': None}]},
          'movies': {'data': [{'radarrId': 24, 'profileId': 8}]},
        }
        return io.BytesIO(json.dumps(responses[endpoint]).encode())
      with patch.object(bazarr.urllib.request, 'urlopen', side_effect=request):
        bazarr.profiles({'dataDir': folder, 'port': 6767, 'profile': {'name': 'English (Nix)'}})
      settings = posts['system/settings']
      self.assertEqual(settings['settings-general-serie_default_enabled'], ['true'])
      self.assertEqual(settings['settings-general-movie_default_profile'], ['8'])
      self.assertEqual(settings['languages-enabled'], ['en', 'fr'])
      self.assertIn(existing, json.loads(settings['languages-profiles'][0]))
      self.assertEqual(posts['series'], {'seriesid': ['12'], 'profileid': ['8']})
      self.assertNotIn('movies', posts)


if __name__ == '__main__':
  unittest.main()
