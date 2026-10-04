import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("usenet", Path(__file__).resolve().parents[1] / "hosts/media/usenet-configure.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UsenetTests(unittest.TestCase):
  def setUp(self):
    self.clients = [{"id": 1, "name": "qBittorrent", "implementation": "QBittorrent", "fields": []}]
    self.writes = []

  def call(self, app, endpoint, method="GET", body=None):
    if endpoint.endswith('/schema'):
      return [{"name": "", "implementation": "Sabnzbd", "fields": [{"name": "apiKey"}, {"name": "tvCategory"}]}]
    if method == "GET":
      return copy.deepcopy(self.clients)
    if endpoint.endswith('/test'):
      return None
    self.writes.append((endpoint, method))
    body = copy.deepcopy(body)
    if method == "POST":
      body['id'] = 2
      self.clients.append(body)
    else:
      self.clients[1] = body

  def reconcile(self):
    return module.reconcile({}, 'downloadclient', 'SABnzbd', 'Sabnzbd',
      {'apiKey': 'runtime-key', 'tvCategory': 'tv'},
      {'enable': True, 'removeCompletedDownloads': True})

  def test_idempotent_and_preserves_torrent(self):
    torrent = copy.deepcopy(self.clients[0])
    with patch.object(module, 'arr', side_effect=self.call):
      self.assertTrue(self.reconcile())
      self.assertFalse(self.reconcile())
    self.assertEqual(self.clients[0], torrent)
    self.assertEqual(self.writes, [('downloadclient', 'POST')])

  def test_name_collision_and_duplicates_fail_closed(self):
    for clients in [
      [{'name': 'SABnzbd', 'implementation': 'QBittorrent'}],
      [{'name': 'SABnzbd', 'implementation': 'Sabnzbd'}] * 2,
    ]:
      with patch.object(module, 'arr', return_value=clients) as call:
        with self.assertRaises(RuntimeError):
          self.reconcile()
      self.assertEqual(call.call_count, 1)

  def test_failed_test_never_saves(self):
    def call(app, endpoint, method="GET", body=None):
      if endpoint.endswith('/test'):
        raise RuntimeError('Unavailable')
      return self.call(app, endpoint, method, body)
    with patch.object(module, 'arr', side_effect=call):
      with self.assertRaises(RuntimeError):
        self.reconcile()
    self.assertEqual(self.writes, [])

  def test_retention_preserves_active_recent_jobs_and_all_files(self):
    old = {'status': 'Completed', 'completed': 1, 'nzo_id': 'old'}
    failed = dict(old, status='Failed', nzo_id='failed')
    active = dict(old, status='Extracting', nzo_id='active')
    recent = dict(old, completed=40 * 86400, nzo_id='recent')
    def api(settings, key, **params):
      if params.get('archive') == 1:
        return {'history': {'slots': []}}
      if params.get('name') == 'delete':
        return {'status': True}
      if params.get('nzo_ids') == 'old':
        return {'history': {'slots': [old]}}
      if params.get('nzo_ids') == 'failed':
        # A retry started after the initial scan; leave it alone.
        return {'history': {'slots': [dict(failed, status='Downloading')]}}
      return {'history': {'slots': [old, failed, active, recent]}}
    with tempfile.TemporaryDirectory() as folder:
      root = Path(folder)
      (root / 'sab-api').write_text('runtime-key')
      with patch.object(module, 'sab', side_effect=api) as call:
        module.retain_history({}, root, now=40 * 86400)
    deletions = [c.kwargs for c in call.call_args_list if c.kwargs.get('name') == 'delete']
    self.assertEqual(deletions, [{'mode': 'history', 'name': 'delete', 'value': 'old', 'del_files': 0, 'archive': 0}])

  def test_http_errors_do_not_expose_secrets(self):
    with patch.object(module.urllib.request, 'urlopen', side_effect=ValueError('sensitive-value')):
      with self.assertRaises(RuntimeError) as caught:
        module.request_json('http://localhost/api?apikey=sensitive-value')
    self.assertNotIn('sensitive-value', str(caught.exception))


if __name__ == '__main__':
  unittest.main()
