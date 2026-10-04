import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from media_import.store import Store, signature, packed
from media_import.cli import execute
from media_import.music_copy import copy_file, state, assert_library_independent


class TaggingApps:
  def __init__(self):
    self.fail = False
    self.scans = 0

  def prepare(self, mapping, media):
    return {'kind':'music', 'app':'lidarr', 'id':1}

  def scan(self, record):
    self.scans += 1
    Path(record['expectedPath']).write_bytes(b'retagged library content')
    if self.fail:
      raise ValueError('interrupted after tagging')

  def verify(self, record, mapping, destination):
    return record


class MusicCopyTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.base = Path(self.temp.name)
    self.root = self.base/'torrents'
    self.source = self.root/'Music/Album/song.flac'
    self.source.parent.mkdir(parents=True)
    self.source.write_bytes(b'original torrent bytes')
    self.media = self.base/'media'
    self.media.mkdir()
    self.store = Store(self.base/'audit.sqlite', self.root)
    self.store.inventory(now=0)
    self.store.inventory(now=601)
    self.revision = self.store.db.execute('SELECT current_revision FROM files').fetchone()[0]
    self.mapping = {'kind':'music', 'identity':{'title':'Album'}, 'entityPath':'music/Artist', 'destination':'music/Artist/Album/song.flac', 'disc':1,'track':1}
    proposal = self.store.propose(self.revision,self.mapping)
    self.store.decide(self.revision,'accept','test',proposal)
    self.batch = self.store.batch([proposal])
    self.op = self.store.db.execute('SELECT id FROM operations').fetchone()[0]
    self.dest = self.media/self.mapping['destination']
    self.config = {'media':str(self.media)}
    self.apps = TaggingApps()

  def tearDown(self):
    self.store.db.close()
    self.temp.cleanup()

  def test_copy_retag_and_repeat_leave_source_untouched(self):
    original = signature(self.source)
    execute(self.store,self.config,self.batch,self.apps)
    self.assertEqual(signature(self.source),original)
    self.assertEqual(self.source.read_bytes(),b'original torrent bytes')
    self.assertEqual(self.dest.read_bytes(),b'retagged library content')
    self.assertFalse(os.path.samefile(self.source,self.dest))
    execute(self.store,self.config,self.batch,self.apps)
    self.assertEqual(self.apps.scans,1)
    execute(self.store,self.config,self.batch,self.apps,verify_only=True,verify_hashes=True)
    self.assertEqual(self.store.inventory(now=800)['changed'],0)
    self.assertEqual(self.store.candidates(),[])

  def test_resume_after_tagging_does_not_recopy_or_compare_library_bytes(self):
    self.apps.fail=True
    with self.assertRaisesRegex(ValueError,'interrupted'):
      execute(self.store,self.config,self.batch,self.apps)
    inode=self.dest.stat().st_ino
    self.apps.fail=False
    execute(self.store,self.config,self.batch,self.apps)
    self.assertEqual(self.dest.stat().st_ino,inode)
    self.assertEqual(self.source.read_bytes(),b'original torrent bytes')

  def test_album_command_resumes_linked_copies_and_skips_verified_tracks(self):
    class AlbumApps(TaggingApps):
      def __init__(self):
        super().__init__()
        self.commands = 0
      def prepare(self, mapping, media):
        return {**super().prepare(mapping,media), 'trackId':mapping['track']}
      def scan_music(self, records):
        self.commands += 1
        for record in records:
          self.scan(record)
    apps = AlbumApps()
    apps.fail = True
    with self.assertRaisesRegex(ValueError,'interrupted'):
      execute(self.store,self.config,self.batch,apps)
    inode = self.dest.stat().st_ino
    apps.fail = False
    execute(self.store,self.config,self.batch,apps)
    execute(self.store,self.config,self.batch,apps)
    self.assertEqual(apps.commands,2)
    self.assertEqual(self.dest.stat().st_ino,inode)
    self.assertEqual(self.source.read_bytes(),b'original torrent bytes')

  def test_two_tracks_use_one_album_command_and_retry_is_noop(self):
    from media_import.store import digest
    second = self.source.parent/'second.flac'
    second.write_bytes(b'second original')
    self.store.inventory(now=800)
    self.store.inventory(now=1401)
    revision = self.store.db.execute("SELECT current_revision FROM files WHERE path LIKE '%second.flac'").fetchone()[0]
    mapping = {**self.mapping, 'track':2, 'destination':'music/Artist/Album/second.flac'}
    proposal = self.store.propose(revision,mapping)
    self.store.decide(revision,'accept','test',proposal)
    batch2 = self.store.batch([proposal])
    manifest = json.loads(self.store.db.execute('SELECT manifest FROM batches WHERE id=?',(self.batch,)).fetchone()[0])
    manifest += json.loads(self.store.db.execute('SELECT manifest FROM batches WHERE id=?',(batch2,)).fetchone()[0])
    self.store.db.execute('UPDATE operations SET batch_id=? WHERE batch_id=?',(self.batch,batch2))
    self.store.db.execute('UPDATE batches SET manifest=?,digest=? WHERE id=?',(packed(manifest),digest(manifest),self.batch))
    self.store.db.commit()
    class AlbumApps(TaggingApps):
      commands = 0
      def prepare(self,mapping,media):
        return {**super().prepare(mapping,media), 'trackId':mapping['track']}
      def scan_music(self,records):
        self.commands += 1
        assert len(records)==2
        for record in records:
          self.scan(record)
    apps = AlbumApps()
    execute(self.store,self.config,self.batch,apps)
    execute(self.store,self.config,self.batch,apps)
    self.assertEqual(apps.commands,1)
    self.assertEqual(second.read_bytes(),b'second original')

  def test_queue_runs_only_explicitly_enqueued_approved_batches(self):
    from media_import.queue import enqueue, work
    with patch('media_import.cli.apply_batch') as apply:
      work(self.store,self.config)
      apply.assert_not_called()
      enqueue(self.store,self.batch)
      work(self.store,self.config)
      work(self.store,self.config)
      apply.assert_called_once_with(self.store,self.config,self.batch)
    self.assertEqual(self.store.db.execute('SELECT status FROM import_jobs').fetchone()[0],'complete')

  def test_queue_failure_is_saved_without_infinite_retry(self):
    from media_import.queue import enqueue, work
    enqueue(self.store,self.batch)
    with patch('media_import.cli.apply_batch',side_effect=ValueError('track mismatch')) as apply:
      work(self.store,self.config)
      work(self.store,self.config)
      self.assertEqual(apply.call_count,1)
    row = self.store.db.execute('SELECT * FROM import_jobs').fetchone()
    self.assertEqual(row['status'],'failed')
    self.assertEqual(row['error'],'track mismatch')

  def test_queue_recovers_a_worker_interrupted_mid_batch(self):
    from media_import.queue import enqueue, work
    enqueue(self.store,self.batch)
    self.store.db.execute("UPDATE import_jobs SET status='running'")
    self.store.db.commit()
    with patch('media_import.cli.apply_batch') as apply:
      work(self.store,self.config)
      apply.assert_called_once_with(self.store,self.config,self.batch)

  def test_existing_unrecorded_destination_is_not_overwritten(self):
    self.dest.parent.mkdir(parents=True)
    self.dest.write_bytes(b'unrelated')
    with self.assertRaisesRegex(ValueError,'Unrecorded'):
      execute(self.store,self.config,self.batch,self.apps)
    self.assertEqual(self.dest.read_bytes(),b'unrelated')

  def test_legacy_link_is_detached_without_changing_source_bytes(self):
    self.dest.parent.mkdir(parents=True)
    os.link(self.source,self.dest)
    copy_file(self.store,self.op,self.source,self.dest,convert=True)
    self.assertFalse(os.path.samefile(self.source,self.dest))
    self.assertEqual(self.source.read_bytes(),self.dest.read_bytes())
    self.dest.write_bytes(b'new tags')
    copy_file(self.store,self.op,self.source,self.dest,convert=True)
    self.assertEqual(self.source.read_bytes(),b'original torrent bytes')

  def test_resume_after_publication_before_database_checkpoint(self):
    with patch('media_import.music_copy.independent',side_effect=ValueError('crash')):
      with self.assertRaisesRegex(ValueError,'crash'):
        copy_file(self.store,self.op,self.source,self.dest)
    self.assertEqual(state(self.store,self.op)['phase'],'ready')
    copy_file(self.store,self.op,self.source,self.dest)
    self.assertEqual(state(self.store,self.op)['phase'],'published')
    self.assertEqual(self.source.read_bytes(),self.dest.read_bytes())

  def test_resume_conversion_after_replace_before_checkpoint(self):
    self.dest.parent.mkdir(parents=True)
    os.link(self.source,self.dest)
    with patch('media_import.music_copy.independent',side_effect=ValueError('crash')):
      with self.assertRaisesRegex(ValueError,'crash'):
        copy_file(self.store,self.op,self.source,self.dest,convert=True)
    copy_file(self.store,self.op,self.source,self.dest,convert=True)
    self.assertEqual(state(self.store,self.op)['phase'],'published')
    self.assertEqual(json.loads(self.store.db.execute('SELECT verified_signature FROM operations').fetchone()[0]),signature(self.source))

  def test_partial_copy_is_recreated_but_source_changes_block_resume(self):
    with patch('media_import.music_copy.checksum',side_effect=ValueError('crash')):
      with self.assertRaisesRegex(ValueError,'crash'):
        copy_file(self.store,self.op,self.source,self.dest)
    self.assertFalse(self.dest.exists())
    copy_file(self.store,self.op,self.source,self.dest)
    self.assertEqual(self.source.read_bytes(),self.dest.read_bytes())

  def test_one_time_library_check_rejects_hardlinks(self):
    self.dest.parent.mkdir(parents=True)
    os.link(self.source,self.dest)
    with self.assertRaisesRegex(ValueError,'Hardlink'):
      assert_library_independent(self.media/'music')
