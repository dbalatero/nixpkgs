import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "hosts/builder/prune-build-logs.py"
SPEC = importlib.util.spec_from_file_location("cleanup", SOURCE)
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


class RetentionTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.directory = Path(self.temporary.name)
    (self.directory / "ab").mkdir()
    self.now = time.time()

  def log(self, name, days):
    path = self.directory / "ab" / name
    path.write_text("test log")
    timestamp = self.now - days * 86400
    os.utime(path, (timestamp, timestamp))
    return path

  def test_only_old_regular_build_logs_expire(self):
    old = self.log("old.drv.bz2", 31)
    old_plain = self.log("old.drv", 31)
    recent = self.log("recent.drv.bz2", 29)
    boundary = self.log("boundary.drv.bz2", 30)
    unrelated = self.log("keep.txt", 40)
    link = self.directory / "ab/link.drv.bz2"
    link.symlink_to(unrelated)
    with patch.object(cleanup, "open_files", return_value=set()):
      self.assertEqual(cleanup.prune(self.directory, now=self.now), 2)
    self.assertFalse(old.exists())
    self.assertFalse(old_plain.exists())
    for path in (recent, boundary, unrelated, link):
      self.assertTrue(path.exists())

  def test_open_old_logs_are_preserved(self):
    old = self.log("active.drv.bz2", 31)
    with old.open("a") as stream:
      info = os.fstat(stream.fileno())
      with patch.object(cleanup, "open_files", return_value={(info.st_dev, info.st_ino)}):
        self.assertEqual(cleanup.prune(self.directory, now=self.now), 0)
    self.assertTrue(old.exists())

  def test_failed_process_inspection_deletes_nothing(self):
    old = self.log("old.drv.bz2", 31)
    with patch.object(cleanup, "open_files", side_effect=PermissionError("restricted proc")):
      with self.assertRaises(PermissionError):
        cleanup.prune(self.directory, now=self.now)
    self.assertTrue(old.exists())

  def test_log_modified_during_inspection_is_preserved(self):
    old = self.log("old.drv.bz2", 31)
    def modified():
      old.write_text("new build output")
      return set()
    with patch.object(cleanup, "open_files", side_effect=modified):
      self.assertEqual(cleanup.prune(self.directory, now=self.now), 0)
    self.assertTrue(old.exists())

  def test_symlinked_directories_are_not_cleaned(self):
    outside = self.directory / "outside"
    outside.mkdir()
    log = outside / "old.drv.bz2"
    log.write_text("keep")
    os.utime(log, (0, 0))
    root = self.directory / "logs"
    root.mkdir()
    (root / "ab").symlink_to(outside)
    self.assertEqual(cleanup.prune(root, now=self.now), 0)
    self.assertTrue(log.exists())


if __name__ == "__main__":
  unittest.main()
