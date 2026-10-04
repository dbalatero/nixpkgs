import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("prowlarr_apps",
  Path(__file__).resolve().parents[1] / "hosts/media/prowlarr-apps.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ApplicationsTest(unittest.TestCase):
  def setUp(self):
    self.settings = {"url": "http://127.0.0.1:9696", "apps": {
      name.lower(): {"implementation": name, "url": f"http://127.0.0.1:{port}",
        "configXml": f"/{name}/config.xml"}
      for name, port in [("Sonarr", 8989), ("Radarr", 7878), ("Lidarr", 8686)]}}
    self.schemas = [{"implementation": name, "configContract": name + "Settings",
      "fields": [{"name": field, "value": value} for field, value in
        [("baseUrl", ""), ("prowlarrUrl", ""), ("apiKey", ""), ("syncCategories", [5000])]]}
      for name in ("Sonarr", "Radarr", "Lidarr")]
    self.apps = []
    self.writes = []

  def call(self, settings, endpoint, method="GET", body=None):
    if endpoint == "applications/schema":
      return copy.deepcopy(self.schemas)
    if method == "GET":
      return copy.deepcopy(self.apps)
    if endpoint.endswith("/test"):
      return None
    self.writes.append((endpoint, method))
    app = copy.deepcopy(body)
    if method == "POST":
      app["id"] = len(self.apps) + 1
      self.apps.append(app)
    else:
      self.apps[app["id"] - 1] = app

  def configure(self):
    with patch.object(module, "call", side_effect=self.call), patch.object(
      module, "api_key", return_value="runtime-secret"):
      module.configure(self.settings)

  def test_create_then_repeat_without_duplicates(self):
    self.configure()
    self.assertEqual(len(self.apps), 3)
    for app in self.apps:
      self.assertEqual(app["syncLevel"], "fullSync")
      fields = {field["name"]: field["value"] for field in app["fields"]}
      self.assertEqual(fields["prowlarrUrl"], self.settings["url"])
      self.assertEqual(fields["apiKey"], "runtime-secret")
      self.assertEqual(fields["syncCategories"], [5000])
    self.writes.clear()
    self.configure()
    self.assertEqual(self.writes, [])

  def test_update_drift_preserves_other_settings(self):
    self.configure()
    self.apps[0]["syncLevel"] = "disabled"
    self.apps[0]["tags"] = [12]
    self.writes.clear()
    self.configure()
    self.assertEqual(self.writes, [("applications/1", "PUT")])
    self.assertEqual(self.apps[0]["tags"], [12])

  def test_duplicate_name_fails_without_writes(self):
    self.configure()
    self.apps.append(copy.deepcopy(self.apps[0]))
    self.writes.clear()
    with self.assertRaisesRegex(RuntimeError, "Duplicate"):
      self.configure()
    self.assertEqual(self.writes, [])

  def test_failed_connection_is_not_saved(self):
    original = self.call
    def failing(settings, endpoint, method="GET", body=None):
      if endpoint.endswith("/test"):
        raise RuntimeError("Connection failed")
      return original(settings, endpoint, method, body)
    with patch.object(module, "call", side_effect=failing), patch.object(
      module, "api_key", return_value="runtime-secret"):
      with self.assertRaisesRegex(RuntimeError, "Connection failed"):
        module.configure(self.settings)
    self.assertEqual(self.writes, [])


if __name__ == "__main__":
  unittest.main()
