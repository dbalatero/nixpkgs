import datetime
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "hosts/media/cwa-log-retention.py"
SPEC = importlib.util.spec_from_file_location("cwa_log_retention", SCRIPT)
retention = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)


class RetentionTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)
    self.now = datetime.datetime(2026, 10, 4, 12, tzinfo=datetime.timezone.utc).timestamp()

  def log(self, relative, content="log\n", age=15):
    path = self.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.utime(path, (self.now - age * retention.DAY,) * 2)
    return path

  def test_only_completed_expired_logs_removed(self):
    expired = self.log("log_archive/completed.log")
    completed = self.log("backup/restore_old/restore.log", "[check_library post]\nOK\n")
    preserved = [
      self.log("log_archive/current.log", age=14),
      self.log("active.log"),
      self.log("log_archive/book.epub"),
      self.log("log_archive/subdir/nested.log"),
      self.log("backup/restore_old/metadata.db.bak"),
      self.log("backup/restore_failed/restore.log", "Restore started\nfailed\n"),
      self.log("backup/other/restore.log", "[check_library post]\n"),
    ]
    self.assertEqual(retention.prune_logs(self.root, self.now), 2)
    self.assertFalse(expired.exists())
    self.assertFalse(completed.exists())
    self.assertTrue(all(path.exists() for path in preserved))

  def test_symlink_files_and_directories_preserved(self):
    outside = self.log("outside/precious.log")
    archive = self.root / "log_archive"
    archive.mkdir()
    (archive / "link.log").symlink_to(outside)
    backup = self.root / "backup"
    backup.mkdir()
    external_restore = self.log("elsewhere/restore.log", "[check_library post]\n")
    (backup / "restore_link").symlink_to(external_restore.parent, target_is_directory=True)
    self.assertEqual(retention.prune_logs(self.root, self.now), 0)
    self.assertTrue(outside.exists())
    self.assertTrue(external_restore.exists())

  def test_history_cutoffs_timezone_formats_and_unrelated_state(self):
    original_timezone = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    def restore_timezone():
      if original_timezone is None:
        os.environ.pop("TZ", None)
      else:
        os.environ["TZ"] = original_timezone
      time.tzset()
    self.addCleanup(restore_timezone)
    cutoff = self.now - 90 * retention.DAY
    db = sqlite3.connect(self.root / "cwa.db")
    self.addCleanup(db.close)
    for table in retention.HISTORY_TABLES:
      db.execute(f'CREATE TABLE "{table}" (timestamp TEXT)')
      zone = datetime.timezone.utc if table == "cwa_user_activity" else None
      boundary = datetime.datetime.fromtimestamp(cutoff, zone).replace(tzinfo=None)
      old = boundary - datetime.timedelta(seconds=1)
      for value in [old.isoformat(" "), old.isoformat("T"), boundary.isoformat(" "), "invalid", None]:
        db.execute(f'INSERT INTO "{table}" VALUES (?)', (value,))
    db.execute("CREATE TABLE cwa_settings (timestamp TEXT, secret TEXT)")
    db.execute("INSERT INTO cwa_settings VALUES ('2000-01-01', 'preserved')")
    db.commit()
    removed = retention.prune_history(self.root, self.now)
    self.assertEqual(removed, {table: 2 for table in retention.HISTORY_TABLES})
    for table in retention.HISTORY_TABLES:
      self.assertEqual(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0], 3)
    self.assertEqual(db.execute("SELECT secret FROM cwa_settings").fetchone()[0], "preserved")

  def test_missing_database_not_created_and_missing_tables_allowed(self):
    self.assertEqual(retention.prune_history(self.root, self.now), {})
    self.assertFalse((self.root / "cwa.db").exists())
    with sqlite3.connect(self.root / "cwa.db") as db:
      db.execute("CREATE TABLE cwa_import (timestamp TEXT)")
      db.execute("INSERT INTO cwa_import VALUES ('2000-01-01 00:00:00')")
    self.assertEqual(retention.prune_history(self.root, self.now), {"cwa_import": 1})

  def test_schema_failure_rolls_back_all_history_deletions(self):
    with sqlite3.connect(self.root / "cwa.db") as db:
      db.execute("CREATE TABLE cwa_import (timestamp TEXT)")
      db.execute("INSERT INTO cwa_import VALUES ('2000-01-01 00:00:00')")
      db.execute("CREATE TABLE cwa_conversions (unexpected TEXT)")
    with self.assertRaises(sqlite3.OperationalError):
      retention.prune_history(self.root, self.now)
    with sqlite3.connect(self.root / "cwa.db") as db:
      self.assertEqual(db.execute("SELECT COUNT(*) FROM cwa_import").fetchone()[0], 1)


if __name__ == "__main__":
  unittest.main()
