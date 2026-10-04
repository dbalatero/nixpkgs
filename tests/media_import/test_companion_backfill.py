import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from media_import.companion_backfill import apply, validate
from media_import.store import Store, packed, signature


class CompanionBackfillTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    base = Path(self.temp.name)
    self.root, self.media = base / 'source', base / 'media'
    (self.root / 'Movies/Release').mkdir(parents=True)
    (self.media / 'movies/Film').mkdir(parents=True)
    self.video = self.root / 'Movies/Release/Film.mkv'
    self.sub = self.root / 'Movies/Release/Film.en.srt'
    self.video.write_bytes(b'video')
    self.sub.write_bytes(b'1\n00:00:01,000 --> 00:00:02,000\nHello\n')
    self.destination = self.media / 'movies/Film/Film.mkv'
    os.link(self.video, self.destination)
    self.store = Store(base / 'audit.sqlite', self.root)
    self.store.inventory(now=0)
    self.store.inventory(now=1000)
    video = self.store.db.execute("SELECT * FROM files WHERE path LIKE '%.mkv'").fetchone()
    sub = self.store.db.execute("SELECT * FROM files WHERE path LIKE '%.srt'").fetchone()
    parent = {'kind': 'movie', 'identity': {'tmdbId': 1}, 'entityPath': 'movies/Film', 'destination': 'movies/Film/Film.mkv'}
    proposal = self.store.propose(video['current_revision'], parent)
    self.store.decide(video['current_revision'], 'accept', 'Reviewed', proposal)
    self.store.batch([proposal])
    self.store.db.execute("UPDATE operations SET status='verified',verified_signature=?", (packed(signature(self.video)),))
    self.store.db.commit()
    self.store.decide(sub['current_revision'], 'exclude', 'Old exclusion')
    self.config = {'source': str(self.root), 'media': str(self.media), 'localBackups': str(base / 'backups')}
    self.plan = {'source': str(self.root), 'media': str(self.media), 'items': [{
      'fileId': sub['id'], 'revision': sub['current_revision'], 'source': sub['path'], 'signature': signature(self.sub),
      'parentOperation': 1, 'parentSource': video['path'], 'parentDestination': parent['destination'],
      'mapping': {**parent, 'kind': 'companion', 'destination': 'movies/Film/Film.en.srt'}}]}

  def tearDown(self):
    self.store.db.close()
    self.temp.cleanup()

  def test_links_and_flips_status_preserving_history_and_is_repeatable(self):
    batch = apply(self.store, self.config, self.plan)
    self.assertTrue(os.path.samefile(self.sub, self.media / 'movies/Film/Film.en.srt'))
    row = next(r for r in self.store.report() if r['source'].endswith('.srt'))
    self.assertEqual(row['state'], 'verified-companion')
    self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM decisions WHERE action='exclude'").fetchone()[0], 1)
    self.assertEqual(apply(self.store, self.config, self.plan), batch)
    self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM operations').fetchone()[0], 2)

  def test_rejects_replaced_parent_and_destination_without_writes(self):
    self.destination.unlink()
    self.destination.write_bytes(b'replacement')
    with self.assertRaisesRegex(ValueError, 'Parent video hardlink'):
      apply(self.store, self.config, self.plan)
    self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM operations').fetchone()[0], 1)

  def test_rejects_changed_source_and_collisions(self):
    (self.media / 'movies/Film/Film.en.srt').write_bytes(b'other subtitles')
    with self.assertRaisesRegex(ValueError, 'Destination collision'):
      validate(self.store, self.config, self.plan)
    self.sub.write_bytes(b'changed')
    with self.assertRaisesRegex(ValueError, 'Subtitle changed'):
      validate(self.store, self.config, self.plan)

  def test_remount_creates_a_new_revision_without_erasing_old_exclusion(self):
    item = self.plan['items'][0]
    old = item['signature'].copy()
    old[3] += 1
    item['inventorySignature'] = old
    self.store.db.execute('UPDATE revisions SET signature=? WHERE id=?', (packed(old), item['revision']))
    self.store.db.commit()
    apply(self.store, self.config, self.plan)
    current = self.store.db.execute('SELECT current_revision FROM files WHERE id=?', (item['fileId'],)).fetchone()[0]
    self.assertNotEqual(current, item['revision'])
    self.assertEqual(self.store.db.execute('SELECT action FROM decisions WHERE revision_id=?', (item['revision'],)).fetchone()[0], 'exclude')

  def test_rejects_duplicate_destinations_and_wrong_identity(self):
    plan = copy.deepcopy(self.plan)
    plan['items'].append(plan['items'][0])
    with self.assertRaisesRegex(ValueError, 'duplicate source'):
      validate(self.store, self.config, plan)
    plan = copy.deepcopy(self.plan)
    plan['items'][0]['mapping']['identity'] = {'tmdbId': 2}
    with self.assertRaisesRegex(ValueError, 'identity differs'):
      validate(self.store, self.config, plan)


if __name__ == '__main__':
  unittest.main()
