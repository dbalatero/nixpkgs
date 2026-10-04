import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from media_import.store import Store, checksum, contained, signature
from media_import.cli import execute, precompute_hashes


class MovieRootTest(unittest.TestCase):
  def test_registers_declared_root_once_preserving_other_roots(self):
    from media_import.apps import Apps
    root = '/mnt/warez/media/movies'
    roots = [{'id': 1, 'path': '/other/movies'}]
    api = Mock()
    def call(endpoint, method='GET', body=None):
      self.assertEqual(endpoint, 'rootfolder')
      if method == 'GET':
        return list(roots)
      self.assertEqual(method, 'POST')
      self.assertEqual(body, {'path': root})
      roots.append({'id': 2, **body})
    api.call.side_effect = call
    apps = Apps({'movieRoot': root})
    with patch.object(apps, 'api', return_value=api) as get_api:
      apps.configure_movie_root()
      apps.configure_movie_root()
    self.assertEqual(roots, [{'id': 1, 'path': '/other/movies'}, {'id': 2, 'path': root}])
    self.assertEqual(api.call.call_count, 3)
    get_api.assert_called_with('radarr')

  def test_undeclared_root_does_not_contact_radarr(self):
    from media_import.apps import Apps
    apps = Apps({})
    with patch.object(apps, 'api') as get_api:
      apps.configure_movie_root()
    get_api.assert_not_called()


class FakeApps:
  def __init__(self):
    self.prepared = 0
    self.scanned = 0
    self.fail = False

  def prepare(self, mapping, media):
    self.prepared += 1
    return {"kind": "filesystem"}

  def scan(self, record):
    self.scanned += 1

  def verify(self, record, mapping, destination):
    if self.fail:
      raise ValueError("Simulated app mismatch")
    return record


class ImportTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.base = Path(self.temp.name)
    self.source = self.base / "torrents"
    self.source.mkdir()
    self.media = self.base / "media"
    self.media.mkdir()
    self.store = Store(self.base / "audit.sqlite", self.source)
    self.config = {"media": str(self.media)}
    self.apps = FakeApps()

  def tearDown(self):
    self.store.db.close()
    self.temp.cleanup()

  def file(self, name="Movies/Example.2020.mkv", data=b"original bytes"):
    path = self.source / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path

  def stable(self):
    self.store.inventory(now=0)
    self.store.inventory(now=601)

  def batch(self, path=None):
    path = path or self.file()
    self.stable()
    row = self.store.db.execute("SELECT current_revision FROM files WHERE path=?", (str(path.relative_to(self.source)),)).fetchone()
    mapping = {"kind": "movie", "identity": {"title": "Example", "tmdbId": 1}, "entityPath": "movies/Example (2020)", "destination": "movies/Example (2020)/Example.mkv"}
    proposal = self.store.propose(row[0], mapping)
    self.store.decide(row[0], "accept", "test review", proposal)
    return self.store.batch([proposal])

  def test_incremental_inventory(self):
    self.file()
    self.assertEqual(self.store.inventory(now=0)["new"], 1)
    self.assertEqual(len(self.store.candidates()), 0)
    self.store.inventory(now=601)
    self.assertEqual(len(self.store.candidates()), 1)
    self.file("TV Shows/New.S01E01.mkv", b"new")
    self.assertEqual(self.store.inventory(now=700)["new"], 1)
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM files").fetchone()[0], 2)

  def test_verified_import_is_noop_on_repeat(self):
    batch = self.batch()
    execute(self.store, self.config, batch, self.apps)
    self.assertEqual(self.store.inventory(now=800)["changed"], 0)
    self.assertEqual(len(self.store.candidates()), 0)
    with patch("media_import.cli.checksum", side_effect=AssertionError("Should not rehash")):
      execute(self.store, self.config, batch, self.apps)
    self.assertEqual(self.apps.prepared, 1)
    self.assertEqual(self.apps.scanned, 1)

  def test_changed_approval_stops(self):
    batch = self.batch()
    self.file(data=b"changed")
    with self.assertRaisesRegex(ValueError, "changed"):
      execute(self.store, self.config, batch, self.apps)
    self.assertEqual(self.apps.prepared, 0)

  def test_changed_import_never_requeues(self):
    batch = self.batch()
    execute(self.store, self.config, batch, self.apps)
    self.file(data=b"changed shared inode")
    self.assertEqual(self.store.inventory(now=800)["changed"], 1)
    self.store.inventory(now=1500)
    self.assertEqual(len(self.store.candidates()), 0)
    with self.assertRaises(ValueError):
      execute(self.store, self.config, batch, self.apps, verify_only=True)

  def test_missing_source_preserves_destination(self):
    batch = self.batch()
    execute(self.store, self.config, batch, self.apps)
    (self.source / "Movies/Example.2020.mkv").unlink()
    self.assertEqual(self.store.inventory()["missing"], 1)
    self.assertTrue((self.media / "movies/Example (2020)/Example.mkv").exists())

  def test_scan_error_does_not_mark_missing(self):
    self.file()
    self.stable()
    def broken_walk(root, **kwargs):
      kwargs["onerror"](PermissionError("no access"))
      return iter([])
    with patch("media_import.store.os.walk", broken_walk):
      result = self.store.inventory()
    self.assertEqual(result["missing"], 0)
    self.assertTrue(result["errors"])
    self.assertEqual(self.store.db.execute("SELECT present FROM files").fetchone()[0], 1)

  def test_destination_collision(self):
    batch = self.batch()
    dest = self.media / "movies/Example (2020)/Example.mkv"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"different library file")
    with self.assertRaisesRegex(ValueError, "collision"):
      execute(self.store, self.config, batch, self.apps)
    self.assertEqual(dest.read_bytes(), b"different library file")

  def test_crash_after_link_recovers(self):
    batch = self.batch()
    actual_link = os.link
    def crash(source, target, **kwargs):
      actual_link(source, target, **kwargs)
      raise OSError("simulated crash after link")
    with patch("media_import.cli.os.link", crash):
      with self.assertRaises(OSError):
        execute(self.store, self.config, batch, self.apps)
    execute(self.store, self.config, batch, self.apps)
    self.assertEqual(self.store.db.execute("SELECT status FROM operations").fetchone()[0], "verified")
    self.assertEqual(self.apps.prepared, 1)

  def test_hash_change_during_recovery_stops(self):
    batch = self.batch()
    self.apps.fail = True
    with self.assertRaises(ValueError):
      execute(self.store, self.config, batch, self.apps)
    self.file(data=b"corrupt")
    with self.assertRaises(ValueError):
      execute(self.store, self.config, batch, self.apps)

  def test_failed_link_never_copies(self):
    batch = self.batch()
    with patch("media_import.cli.os.link", side_effect=OSError("EXDEV")):
      with self.assertRaises(OSError):
        execute(self.store, self.config, batch, self.apps)
    self.assertFalse((self.media / "movies/Example (2020)/Example.mkv").exists())

  def test_app_failure_is_not_verified(self):
    batch = self.batch()
    self.apps.fail = True
    with self.assertRaises(ValueError):
      execute(self.store, self.config, batch, self.apps)
    op = self.store.db.execute("SELECT status,error FROM operations").fetchone()
    self.assertEqual(op["status"], "linked")
    self.assertTrue(op["error"])
    self.apps.fail = False
    execute(self.store, self.config, batch, self.apps, verify_only=True)
    self.assertEqual(self.store.db.execute("SELECT status FROM operations").fetchone()[0], "verified")

  def test_backup_restores_decisions(self):
    self.batch()
    backup = self.store.backup(self.base / "backups")
    restored = Store(backup, self.source)
    self.assertEqual(restored.db.execute("SELECT action FROM decisions").fetchone()[0], "accept")
    self.assertEqual(restored.db.execute("SELECT count(*) FROM batches").fetchone()[0], 1)
    restored.db.close()

  def test_backup_retention_reuse_and_forced_snapshot(self):
    directory = self.base / 'backups'
    first = self.store.backup(directory)
    self.assertEqual(self.store.backup(directory), first)
    unrelated = directory / 'notes.sqlite'
    unrelated.write_text('preserve')
    snapshots = [first] + [self.store.backup(directory, force=True) for _ in range(4)]
    self.assertEqual(set(directory.glob('audit-*.sqlite')), set(snapshots[-3:]))
    self.assertTrue(unrelated.exists())
    self.assertFalse(list(directory.glob('*.partial')))
    stale = directory / '.audit-123.sqlite.partial'
    stale.write_text('interrupted')
    self.store.backup(directory)
    self.assertFalse(stale.exists())

  def test_traversal_and_symlink_rejected(self):
    with self.assertRaises(ValueError):
      contained(self.media, "../escape")
    (self.media / "link").symlink_to(self.source)
    with self.assertRaises(ValueError):
      contained(self.media, "link/file")

  def test_same_bytes_new_path_is_separate_record(self):
    self.file()
    self.file("Movies/Other.mkv")
    self.stable()
    self.assertEqual(len(self.store.candidates()), 2)

  def test_revoke_decision_blocks_approved_batch(self):
    batch = self.batch()
    revision = self.store.db.execute("SELECT current_revision FROM files").fetchone()[0]
    self.store.decide(revision, "defer", "identity uncertain")
    with self.assertRaisesRegex(ValueError, "revoked"):
      execute(self.store, self.config, batch, self.apps)

  def test_archive_cannot_be_disguised_as_movie(self):
    batch = self.batch(self.file("Movies/Example.zip"))
    with self.assertRaisesRegex(ValueError, "Archives"):
      execute(self.store, self.config, batch, self.apps)

  def test_partial_cannot_be_disguised_as_movie(self):
    batch = self.batch(self.file("Movies/Example.mkv.part"))
    with self.assertRaisesRegex(ValueError, "partial"):
      execute(self.store, self.config, batch, self.apps)

  def test_retry_does_not_reopen_decision(self):
    self.batch()
    self.assertEqual(self.store.candidates(retry=True), [])

  def test_new_file_does_not_reset_import(self):
    batch = self.batch()
    execute(self.store, self.config, batch, self.apps)
    self.file("Movies/New.mkv", b"new material")
    self.store.inventory(now=800)
    self.store.inventory(now=1500)
    candidates = self.store.candidates()
    self.assertEqual([r["path"] for r in candidates], ["Movies/New.mkv"])
    self.assertEqual(self.store.db.execute("SELECT status FROM operations").fetchone()[0], "verified")

  def test_report_retains_library_when_source_disappears(self):
    batch = self.batch()
    execute(self.store, self.config, batch, self.apps)
    (self.source / "Movies/Example.2020.mkv").unlink()
    self.store.inventory()
    row = list(self.store.report())[0]
    self.assertEqual(row["state"], "missing-source")
    self.assertEqual(row["destination"], "movies/Example (2020)/Example.mkv")
    self.assertIsNone(row["sha256"])

  def test_noop_does_not_replay_completed_app_calls(self):
    batch = self.batch()
    execute(self.store, self.config, batch, self.apps)
    with patch.object(self.apps, "prepare", side_effect=AssertionError("replayed")), patch.object(self.apps, "scan", side_effect=AssertionError("rescanned")):
      execute(self.store, self.config, batch, self.apps)

  def test_replaced_inode_with_same_size_and_mtime_is_detected(self):
    source = self.file()
    self.stable()
    old = source.stat()
    replacement = source.with_suffix(".replacement")
    replacement.write_bytes(source.read_bytes())
    os.utime(replacement, ns=(old.st_atime_ns, old.st_mtime_ns))
    replacement.replace(source)
    self.assertEqual(self.store.inventory(now=800)["changed"], 1)

  def test_source_rewrite_during_scan_is_not_verified(self):
    batch = self.batch()
    def rewrite(record):
      (self.source / "Movies/Example.2020.mkv").write_bytes(b"changed by app")
    with patch.object(self.apps, "scan", rewrite):
      with self.assertRaisesRegex(ValueError, "content changed"):
        execute(self.store, self.config, batch, self.apps)
    self.assertNotEqual(self.store.db.execute("SELECT status FROM operations").fetchone()[0], "verified")

  def test_existing_app_file_blocks_replacement(self):
    batch = self.batch()
    with patch.object(self.apps, "prepare", return_value={"kind": "movie", "existingPaths": ["/different/movie.mkv"]}):
      with self.assertRaisesRegex(ValueError, "replacement"):
        execute(self.store, self.config, batch, self.apps)
    self.assertFalse((self.media / "movies/Example (2020)/Example.mkv").exists())

  def hash_config(self):
    return {**self.config, "database": str(self.store.path), "source": str(self.source), "stabilitySeconds": 600}

  def test_hash_worker_resumes_and_excludes_imported_files(self):
    self.batch()
    self.file("Movies/New.mkv")
    self.stable()
    with patch("media_import.cli.mount_check"):
      first = precompute_hashes(self.hash_config())
      with patch("media_import.cli.checksum", side_effect=AssertionError("Rehashed")):
        second = precompute_hashes(self.hash_config())
    self.assertEqual(first["hashed"], 1)
    self.assertEqual(second["cached"], 1)

  def test_cached_apply_does_not_read_file_contents(self):
    source = self.file()
    self.stable()
    revision = self.store.db.execute("SELECT current_revision FROM files").fetchone()[0]
    self.store.save_hash(revision, signature(source), checksum(source))
    batch = self.batch(source)
    with patch("media_import.cli.checksum", side_effect=AssertionError("Rehashed")):
      execute(self.store, self.config, batch, self.apps)
    self.assertEqual(self.store.db.execute("SELECT status FROM operations").fetchone()[0], "verified")

  def test_changed_hash_is_not_reused(self):
    source = self.file()
    self.stable()
    revision = self.store.db.execute("SELECT current_revision FROM files").fetchone()[0]
    self.store.save_hash(revision, signature(source), checksum(source))
    source.write_bytes(b"different")
    self.assertIsNone(self.store.cached_hash(revision, signature(source)))

  def test_worker_discards_changed_file_and_releases_lock_while_hashing(self):
    import fcntl
    source = self.file()
    self.stable()
    def changing_checksum(path, progress=None):
      with (self.base / "audit.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
      value = checksum(path)
      source.write_bytes(b"changed while worker was busy")
      return value
    with patch("media_import.cli.mount_check"), patch("media_import.cli.checksum", side_effect=changing_checksum):
      result = precompute_hashes(self.hash_config())
    self.assertEqual(result["skipped"], 1)
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM hashes").fetchone()[0], 0)

  def test_explicit_verify_bypasses_hash_cache(self):
    batch = self.batch()
    execute(self.store, self.config, batch, self.apps)
    with patch("media_import.cli.checksum", wraps=checksum) as hashing:
      execute(self.store, self.config, batch, self.apps, verify_only=True, verify_hashes=True)
    self.assertGreaterEqual(hashing.call_count, 1)

  def test_cached_source_rewrite_during_prepare_is_rejected(self):
    source = self.file()
    self.stable()
    revision = self.store.db.execute("SELECT current_revision FROM files").fetchone()[0]
    self.store.save_hash(revision, signature(source), checksum(source))
    batch = self.batch(source)
    def rewrite(mapping, media):
      source.write_bytes(b"modified by another process")
      return {"kind": "filesystem"}
    with patch.object(self.apps, "prepare", side_effect=rewrite):
      with self.assertRaisesRegex(ValueError, "changed during app preparation"):
        execute(self.store, self.config, batch, self.apps)
    self.assertFalse((self.media / "movies/Example (2020)/Example.mkv").exists())

  def test_hash_progress_reports_bytes_and_completion(self):
    import io
    from media_import.cli import HashProgress
    with patch("sys.stdout", new_callable=io.StringIO) as output:
      progress = HashProgress(100)
      progress.file_size = 100
      progress.update(25, force=True)
      progress.update(100, force=True)
      progress.finish_file(100)
      text = output.getvalue()
    self.assertIn("25.00%", text)
    self.assertIn("100.00%", text)
    self.assertIn("ETA", text)
    self.assertEqual(progress.read, 100)

  def test_checksum_reports_incremental_byte_counts(self):
    source = self.file(data=b"x" * (9 * 1024 * 1024))
    counts = []
    checksum(source, progress=counts.append)
    self.assertEqual(counts, [8 * 1024 * 1024, 9 * 1024 * 1024])

  def test_apply_and_verify_without_hashes_never_read_contents(self):
    batch = self.batch()
    with patch("media_import.cli.checksum", side_effect=AssertionError("Unexpected hashing")):
      execute(self.store, self.config, batch, self.apps)
      execute(self.store, self.config, batch, self.apps, verify_only=True)
    self.assertEqual(self.store.db.execute("SELECT status FROM operations").fetchone()[0], "verified")
    self.assertIsNone(self.store.db.execute("SELECT before_hash FROM operations").fetchone()[0])

  def proposal(self):
    self.file()
    self.stable()
    row = self.store.db.execute("SELECT id,current_revision FROM files").fetchone()
    mapping = {"kind": "movie", "identity": {"title": "Example", "tmdbId": 1}, "entityPath": "movies/Example (2020)", "destination": "movies/Example (2020)/Example.mkv"}
    proposal = self.store.propose(row["current_revision"], {"options": [mapping]})
    return row, mapping, proposal

  def test_single_key_review_saves_selection_but_quit_never_imports(self):
    from media_import.cli import review, pending_proposals
    row, mapping, proposal = self.proposal()
    with patch("media_import.cli.key_choice", side_effect=["1", "y"]):
      self.assertTrue(review(self.store, self.config))
    self.assertEqual(len(pending_proposals(self.store)), 1)
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM operations").fetchone()[0], 0)

  def test_review_quit_saves_no_batch(self):
    from media_import.cli import review
    self.proposal()
    with patch("media_import.cli.key_choice", return_value="q"):
      self.assertFalse(review(self.store, self.config))
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM batches").fetchone()[0], 0)

  def test_declining_import_retains_selection_without_creating_batch(self):
    from media_import.cli import approve_batch
    row, mapping, _ = self.proposal()
    proposal = self.store.propose(row["current_revision"], mapping)
    self.store.decide(row["current_revision"], "accept", "test", proposal)
    with patch("media_import.cli.key_choice", return_value="n"):
      self.assertIsNone(approve_batch(self.store, self.config, [proposal], importing=True))
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM batches").fetchone()[0], 0)

  def test_interactive_session_imports_only_after_final_yes(self):
    from argparse import Namespace
    from media_import.cli import interactive_import
    self.proposal()
    config = {**self.config, "localBackups": str(self.base / "backups")}
    args = Namespace(command="review", files=None, kind=None, limit=10)
    with patch("media_import.cli.key_choice", side_effect=["1", "y", "y"]), patch("media_import.cli.mount_check"), patch("media_import.cli.apply_batch") as apply:
      interactive_import(self.store, config, args)
    apply.assert_called_once()
    manifest = json.loads(self.store.db.execute("SELECT manifest FROM batches").fetchone()[0])
    self.assertEqual(len(manifest), 1)
    self.assertEqual(manifest[0]["mapping"]["identity"]["tmdbId"], 1)

  def test_saved_selection_quit_never_reaches_import(self):
    from argparse import Namespace
    from media_import.cli import interactive_import
    row, mapping, _ = self.proposal()
    proposal = self.store.propose(row["current_revision"], mapping)
    self.store.decide(row["current_revision"], "accept", "test", proposal)
    args = Namespace(command="review", files=None, kind=None, limit=10)
    with patch("media_import.cli.key_choice", return_value="q"), patch("media_import.cli.apply_batch") as apply:
      interactive_import(self.store, self.config, args)
    apply.assert_not_called()
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM batches").fetchone()[0], 0)

  def test_status_reads_committed_records_while_import_locks_are_held(self):
    import contextlib
    import fcntl
    import io
    from media_import.cli import main
    self.proposal()
    config = self.hash_config()
    path = self.base / 'config.json'
    path.write_text(json.dumps(config))
    with contextlib.ExitStack() as stack:
      for name in ('coord.lock', 'audit.lock'):
        lock = stack.enter_context((self.store.path.parent / name).open('a'))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
      self.store.db.execute("UPDATE files SET kind='uncommitted'")
      output = io.StringIO()
      with patch('sys.argv', ['media-import', '--config', str(path), 'status']), contextlib.redirect_stdout(output):
        main()
      self.assertIn('movie', output.getvalue())
      self.assertNotIn('uncommitted', output.getvalue())
      self.store.db.rollback()

  def test_tv_prepare_reconciles_duplicate_episode_records(self):
    from unittest.mock import Mock
    from media_import.apps import Apps
    api = Mock()
    episodes = [[{'id':1,'seasonNumber':4,'episodeNumber':3},
      {'id':2,'seasonNumber':4,'episodeNumber':3}],
      [{'id':1,'seasonNumber':4,'episodeNumber':3}]]
    def call(endpoint, **kwargs):
      if endpoint == 'episode':
        return episodes.pop(0)
      return {'system/status':{'version':'test'}, 'qualityprofile':[{'id':1}],
        'series':[{'id':24,'tvdbId':400267,'path':'/media/tv/Ghosts','monitored':False}],
        'episodefile':[]}[endpoint]
    api.call.side_effect = call
    apps = Apps({})
    mapping = {'kind':'tv','identity':{'tvdbId':400267},'entityPath':'tv/Ghosts',
      'appVersion':'test','season':4,'episodes':[3]}
    with patch.object(apps,'api',return_value=api), patch.object(apps,'safety'):
      result = apps.prepare(mapping,Path('/media'))
    self.assertEqual(result['episodeIds'],[1])
    self.assertEqual(api.command.call_count,2)
    duplicate = [{'id':1,'seasonNumber':4,'episodeNumber':3},
      {'id':2,'seasonNumber':4,'episodeNumber':3}]
    episodes.extend([duplicate,duplicate])
    with patch.object(apps,'api',return_value=api), patch.object(apps,'safety'):
      with self.assertRaisesRegex(ValueError,'duplicate records'):
        apps.prepare(mapping,Path('/media'))

  def test_tv_verify_reconciles_late_duplicates_but_rejects_wrong_episode(self):
    from unittest.mock import Mock
    from media_import.apps import Apps
    api = Mock()
    correct = {'id':1,'seasonNumber':1,'episodeNumber':1,'episodeFileId':9}
    duplicate = dict(correct,id=2,episodeFileId=0)
    api.call.side_effect = [[correct,duplicate],[{'id':9,'path':'/media/file.mkv'}],
      [correct],[{'id':9,'path':'/media/file.mkv'}]]
    apps = Apps({})
    record = {'kind':'tv','app':'sonarr','id':25,'episodeIds':[1,2]}
    mapping = {'season':1,'episodes':[1]}
    with patch.object(apps,'api',return_value=api):
      result = apps.verify(record,mapping,Path('/media/file.mkv'))
    self.assertEqual(result['episodeIds'],[1])
    self.assertEqual(api.command.call_count,2)
    wrong = dict(correct,id=3,episodeNumber=2)
    api.call.side_effect = [[dict(correct,episodeFileId=0),wrong],[{'id':9,'path':'/media/file.mkv'}]]
    with patch.object(apps,'api',return_value=api):
      with self.assertRaisesRegex(ValueError,'assignment differs'):
        apps.verify(record,mapping,Path('/media/file.mkv'))

  def test_tv_group_rejects_other_source_titles_with_same_search_candidate(self):
    from media_import.cli import same_tv_source
    def mapping(title):
      return {'identity':{'tvdbId':334185}, 'season':1,
        'evidence':{'guess':{'title':title}}}
    tour = mapping('Mike Judge Presents Tales From the Tour Bus')
    beavis = mapping("Mike Judge's Beavis and Butt-Head")
    self.assertFalse(same_tv_source(tour,beavis))
    self.assertTrue(same_tv_source(tour,mapping('Mike.Judge.Presents.Tales.From.the.Tour.Bus')))
    self.assertFalse(same_tv_source({},{}))

  def test_explicit_tv_token_wins_over_numeric_episode_title(self):
    from media_import.cli import mapping_for
    candidate = {'title':'Ted Lasso','year':2020,'tvdbId':383203}
    evidence = {'guess':{'season':3,'episode':[3,4,5]}}
    mapping = mapping_for('tv','Ted.Lasso.S03E03.4-5-1.mkv',candidate,evidence,'test')
    self.assertEqual(mapping['episodes'],[3])
    self.assertIn('S03E03 - ',mapping['destination'])
    multi = mapping_for('tv','Show.S03E03E04.mkv',candidate,evidence,'test')
    self.assertEqual(multi['episodes'],[3,4])
    ranged = mapping_for('tv','Show.S03E03-05.mkv',candidate,evidence,'test')
    self.assertEqual(ranged['episodes'],[3,4,5])

  def test_default_command_enters_guided_run(self):
    from media_import.cli import main
    config = {**self.hash_config(), "localBackups": str(self.base / "backups")}
    path = self.base / "config.json"
    path.write_text(json.dumps(config))
    with patch("sys.argv", ["media-import", "--config", str(path)]), patch("media_import.cli.mount_check"), patch("media_import.cli.interactive_import") as interactive:
      main()
    args = interactive.call_args.args[2]
    self.assertEqual(args.command, "run")
    self.assertEqual(args.limit, 10)
    self.assertIn("movie", args.kind)

  def test_enter_declines_final_confirmation(self):
    from media_import.cli import key_choice
    with patch("sys.stdin.isatty", return_value=False), patch("builtins.input", return_value=""):
      self.assertEqual(key_choice("Import? [y/N]: ", ["y", "n"], "n"), "n")

  def test_audiobookshelf_scan_waits_for_exact_audio_file(self):
    from media_import.apps import Apps
    from unittest.mock import Mock
    apps = Apps({})
    api = Mock()
    record = {"app": "audiobookshelf", "kind": "audiobook", "libraryId": "library",
      "expectedPath": "/library/second.mp3", "identity": {"title": "Book", "author": "Author"}}
    stale = {"id": "book", "media": {"audioFiles": [{"metadata": {"path": "/library/first.mp3"}}]}}
    complete = {"id": "book", "media": {"audioFiles": [{"metadata": {"path": "/library/second.mp3"}}]}}
    with patch.object(apps, "api", return_value=api), patch.object(apps, "book_item", side_effect=[stale, complete]) as lookup, patch("media_import.apps.time.sleep") as sleep:
      apps.scan(record)
    self.assertEqual(lookup.call_count, 2)
    sleep.assert_called_once_with(2)
    self.assertEqual(api.call.call_args_list[-1].args[0], "items/book/media")

  def test_shared_book_rejects_duplicate_part_numbers(self):
    from media_import.store import validate_book_mappings
    base = {"kind": "spoken-word", "identity": {"title": "Collection", "author": "Author"}, "entityPath": "spoken-word/Collection", "order": 1}
    manifest = [{"mapping": {**base, "destination": "spoken-word/Collection/one.mp3"}},
      {"mapping": {**base, "destination": "spoken-word/Collection/two.mp3"}}]
    with self.assertRaisesRegex(ValueError, "Conflicting audio part"):
      validate_book_mappings(manifest)
    manifest[1]["mapping"]["order"] = 2
    validate_book_mappings(manifest)

  def test_hardcore_history_episode_mapping_preserves_number_and_title(self):
    from media_import.cli import hardcore_history_mapping
    mapping = hardcore_history_mapping("Books/Dan Carlins Hardcore History/dchha02 - Guns & Horses.mp3")
    self.assertEqual(mapping["identity"]["title"], "Guns & Horses")
    self.assertEqual(mapping["identity"]["series"], [{"name": "Hardcore History", "sequence": "2"}])
    self.assertEqual(mapping["order"], 1)
    self.assertIn("002 - Guns & Horses", mapping["destination"])

  def test_hardcore_history_repair_preserves_history_sources_and_is_repeatable(self):
    from media_import.repair_hardcore_history import repair
    from unittest.mock import Mock
    sources = [self.file(f"Books/Dan Carlins Hardcore History/dchha0{i} - Episode {i}.mp3") for i in (1, 2)]
    self.stable()
    proposals = []
    old_folder = self.media / "spoken-word/Dan Carlin/dancarlin.com"
    old_folder.mkdir(parents=True)
    for source in sources:
      revision = self.store.db.execute("SELECT current_revision FROM files WHERE path=?", (str(source.relative_to(self.source)),)).fetchone()[0]
      mapping = {"kind": "spoken-word", "identity": {"title": "dancarlin.com", "author": "Dan Carlin"}, "entityPath": "spoken-word/Dan Carlin/dancarlin.com", "destination": "spoken-word/Dan Carlin/dancarlin.com/" + source.name, "order": 1}
      proposal = self.store.propose(revision, mapping)
      self.store.decide(revision, "accept", "original review", proposal)
      proposals.append(proposal)
    with patch("media_import.store.validate_book_mappings"):
      batch = self.store.batch(proposals)
    original = self.store.db.execute("SELECT manifest FROM batches WHERE id=?", (batch,)).fetchone()[0]
    os.link(sources[0], old_folder / sources[0].name)
    self.store.db.execute("UPDATE operations SET status='verified',app_record=?,verified_signature=? WHERE proposal_id=?", (json.dumps({"kind": "filesystem"}), json.dumps(signature(sources[0])), proposals[0]))
    self.store.db.commit()
    inodes = [p.stat().st_ino for p in sources]
    api = Mock()
    api.call.return_value = {"libraries": []}
    self.apps.api = Mock(return_value=api)
    config = {**self.hash_config(), "localBackups": str(self.base / "backups")}
    with patch("media_import.cli.Apps", return_value=self.apps), patch("media_import.repair_hardcore_history.Apps", return_value=self.apps):
      repair(self.store, config, batch)
      repair(self.store, config, batch)
    self.assertEqual([p.stat().st_ino for p in sources], inodes)
    self.assertFalse(old_folder.exists())
    self.assertEqual(self.store.db.execute("SELECT manifest FROM batches WHERE id=?", (batch,)).fetchone()[0], original)
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM batches").fetchone()[0], 2)
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM operations WHERE status='verified'").fetchone()[0], 2)
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM operations WHERE status='superseded'").fetchone()[0], 2)

  def test_hardcore_history_underscore_names(self):
    from media_import.cli import hardcore_history_mapping
    for filename, title, number in [("dchha11_Thoughts_on_Churchill_.mp3", "Thoughts on Churchill", "11"), ("dchha42__BLITZ_Logical_Insanity.mp3", "BLITZ Logical Insanity", "42")]:
      mapping = hardcore_history_mapping(filename)
      self.assertEqual(mapping["identity"]["title"], title)
      self.assertEqual(mapping["identity"]["series"][0]["sequence"], number)
      self.assertEqual(mapping["kind"], "podcast")
      self.assertTrue(mapping["destination"].startswith("podcasts/"))

  def test_library_relocation_preserves_historical_manifest(self):
    batch = self.batch()
    original = self.store.db.execute("SELECT manifest,digest FROM batches WHERE id=?", (batch,)).fetchone()
    self.store.db.execute("INSERT INTO meta VALUES ('library_relocations', ?)", (json.dumps([["spoken-word", "podcasts"]]),))
    self.store.db.commit()
    mapping = {"kind": "spoken-word", "entityPath": "spoken-word/Author/Book", "destination": "spoken-word/Author/Book/one.mp3"}
    relocated = self.store.relocate_mapping(mapping)
    self.assertEqual(mapping["kind"], "spoken-word")
    self.assertEqual(relocated["kind"], "podcast")
    self.assertEqual(relocated["destination"], "podcasts/Author/Book/one.mp3")
    record = self.store.relocate_record({"bookPath": str(self.media / "spoken-word/Author/Book")}, self.media)
    self.assertEqual(record["bookPath"], str(self.media / "podcasts/Author/Book"))
    self.assertEqual(tuple(original), tuple(self.store.db.execute("SELECT manifest,digest FROM batches WHERE id=?", (batch,)).fetchone()))


if __name__ == "__main__":
  unittest.main()
