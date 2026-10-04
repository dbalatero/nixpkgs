"""Download integration must preserve the importer's source protection policy."""
import unittest
from unittest.mock import Mock, patch

from tools.media_import.apps import Apps


class TorrentPolicyTest(unittest.TestCase):
  def setUp(self):
    self.desired = {
      "name": "qBittorrent",
      "fields": {"host": "127.0.0.1", "port": 8080, "musicCategory": "music"},
    }
    self.client = {
      "name": "qBittorrent", "implementation": "QBittorrent",
      "removeCompletedDownloads": False, "removeFailedDownloads": False,
      "fields": [{"name": key, "value": value} for key, value in self.desired["fields"].items()],
    }
    self.config = {"policy": {"lidarr": {}}, "torrentClients": {"lidarr": self.desired}}
    self.indexers = []
    self.importlists = []
    self.profiles = []
    self.api = Mock()
    self.api.call.side_effect = lambda endpoint: {
      "downloadclient": [self.client], "indexer": self.indexers, "importlist": self.importlists,
      "qualityprofile": self.profiles, "system/status": {"version": "test"},
    }[endpoint]

  def check(self):
    apps = Apps(self.config)
    with patch.object(apps, "api", return_value=self.api):
      return apps.safety("lidarr")

  def test_declared_client_is_allowed(self):
    self.assertEqual(self.check(), "test")

  def test_removing_source_downloads_is_rejected(self):
    self.client["removeCompletedDownloads"] = True
    with self.assertRaisesRegex(ValueError, "unsafe download client"):
      self.check()

  def test_wrong_category_is_rejected(self):
    self.client["fields"][-1]["value"] = "other"
    with self.assertRaisesRegex(ValueError, "unsafe download client"):
      self.check()

  def test_undeclared_client_is_rejected(self):
    self.config.pop("torrentClients")
    with self.assertRaisesRegex(ValueError, "unsafe download client"):
      self.check()

  def test_indexers_still_require_separate_configuration(self):
    self.indexers.append({"name": "unapproved"})
    with self.assertRaisesRegex(ValueError, "indexer entries"):
      self.check()

  def prowlarr_indexer(self, url='http://127.0.0.1:9696/2/', implementation='Torznab'):
    self.config['prowlarrUrl'] = 'http://127.0.0.1:9696'
    return {'implementation': implementation, 'fields': [
      {'name': 'baseUrl', 'value': url}, {'name': 'apiPath', 'value': '/api'}]}

  def test_declared_prowlarr_indexers_are_allowed(self):
    for implementation in ('Torznab', 'Newznab'):
      for url in ('http://127.0.0.1:9696/1/', 'http://127.0.0.1:9696/23'):
        with self.subTest(implementation=implementation, url=url):
          self.indexers[:] = [self.prowlarr_indexer(url, implementation)]
          self.assertEqual(self.check(), 'test')

  def test_other_indexer_urls_are_rejected(self):
    for url in ('http://other:9696/2/', 'http://127.0.0.1:9697/2/',
        'http://127.0.0.1:9696.evil/2/', 'http://127.0.0.1:9696@evil/2/',
        'http://127.0.0.1:9696/', 'http://127.0.0.1:9696/2/../3/',
        'http://127.0.0.1:9696/2/?url=other'):
      with self.subTest(url=url):
        self.indexers[:] = [self.prowlarr_indexer(url)]
        with self.assertRaisesRegex(ValueError, 'undeclared indexer'):
          self.check()

  def test_prowlarr_must_be_declared(self):
    self.indexers.append(self.prowlarr_indexer())
    self.config['prowlarrUrl'] = None
    with self.assertRaisesRegex(ValueError, 'undeclared indexer'):
      self.check()

  def test_unknown_indexer_implementation_is_rejected(self):
    self.indexers.append(self.prowlarr_indexer(implementation='Other'))
    with self.assertRaisesRegex(ValueError, 'undeclared indexer'):
      self.check()

  def test_other_api_path_is_rejected(self):
    indexer = self.prowlarr_indexer()
    indexer['fields'][1]['value'] = '/other'
    self.indexers.append(indexer)
    with self.assertRaisesRegex(ValueError, 'undeclared indexer'):
      self.check()

  def test_prowlarr_does_not_allow_import_lists(self):
    self.indexers.append(self.prowlarr_indexer())
    self.importlists.append({'id': 1})
    with self.assertRaisesRegex(ValueError, 'importlist entries'):
      self.check()

  def test_prowlarr_does_not_allow_upgrades(self):
    self.indexers.append(self.prowlarr_indexer())
    self.profiles.append({'id': 1, 'upgradeAllowed': True})
    with self.assertRaisesRegex(ValueError, 'permits upgrades'):
      self.check()

  def test_prowlarr_does_not_allow_source_removal(self):
    self.indexers.append(self.prowlarr_indexer())
    self.client['removeFailedDownloads'] = True
    with self.assertRaisesRegex(ValueError, 'unsafe download client'):
      self.check()
