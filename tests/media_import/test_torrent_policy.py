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
    self.api = Mock()
    self.api.call.side_effect = lambda endpoint: {
      "downloadclient": [self.client], "indexer": self.indexers, "importlist": [],
      "qualityprofile": [], "system/status": {"version": "test"},
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
