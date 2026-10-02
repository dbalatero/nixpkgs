import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from media_import.store import Store, checksum, contained, signature
from media_import.cli import execute


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
    self.assertTrue(row["sha256"])

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


if __name__ == "__main__":
  unittest.main()
