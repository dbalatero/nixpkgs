#!/usr/bin/env python3
"""Expire CWA logs/history without deleting library, backup, or queue data."""

import argparse
import datetime
import json
import os
from pathlib import Path
import sqlite3
import stat
import time


HISTORY_TABLES = (
  "cwa_import",
  "cwa_conversions",
  "cwa_enforcement",
  "epub_fixes",
  "cwa_user_activity",
  "cwa_duplicate_resolutions",
)
DAY = 24 * 60 * 60


def regular_file(path, root):
  """Refuse symlinks, including any directory between the root and file."""
  for ancestor in (path, *path.parents):
    if ancestor == root:
      break
    if ancestor.is_symlink():
      return False
  try:
    return stat.S_ISREG(path.lstat().st_mode)
  except FileNotFoundError:
    return False


def prune_logs(root, now):
  removed = 0
  candidates = [(path, False) for path in (root / "log_archive").glob("*.log")]
  candidates += [(path, True) for path in (root / "backup").glob("restore_*/restore.log")]
  for path, restore in candidates:
    if not regular_file(path, root):
      continue
    before = path.stat()
    if before.st_mtime >= now - 14 * DAY:
      continue
    if restore:
      # CWA writes this section after its final check subprocess finishes.
      # Failed/incomplete restores lack it and remain available for review.
      with path.open("rb") as stream:
        if not any(line.strip() == b"[check_library post]" for line in stream):
          continue
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
      after.st_ino, after.st_size, after.st_mtime_ns
    ):
      continue
    path.unlink()
    removed += 1
  return removed


def prune_history(root, now):
  database = root / "cwa.db"
  if not regular_file(database, root):
    return {}
  cutoff = now - 90 * DAY
  # Upstream cwa_db.py stamps most tables in local time. User activity uses
  # SQLite's CURRENT_TIMESTAMP default, which is UTC. The service TZ must
  # match the container. Older duplicate-resolution defaults were also UTC;
  # those legacy records may expire a few hours either side of 90 days.
  local_cutoff = datetime.datetime.fromtimestamp(cutoff).isoformat(" ", timespec="seconds")
  utc_cutoff = datetime.datetime.fromtimestamp(cutoff, datetime.timezone.utc).isoformat(" ", timespec="seconds")
  connection = sqlite3.connect(f"{database.as_uri()}?mode=rw", uri=True, timeout=30)
  try:
    with connection:
      connection.execute("PRAGMA busy_timeout = 30000")
      connection.execute("BEGIN IMMEDIATE")
      tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
      removed = {}
      for table in HISTORY_TABLES:
        if table not in tables:
          continue
        # Only fixed allowlisted identifiers are interpolated. Unparseable
        # timestamps yield NULL and are preserved rather than guessed at.
        threshold = utc_cutoff if table == "cwa_user_activity" else local_cutoff
        cursor = connection.execute(
          f'DELETE FROM "{table}" WHERE datetime(timestamp) < datetime(?)',
          (threshold,),
        )
        removed[table] = cursor.rowcount
    return removed
  finally:
    connection.close()


def retain(root, now=None):
  root = Path(root).absolute()
  if root.is_symlink():
    raise ValueError("Refusing a symlinked configuration root")
  now = time.time() if now is None else now
  return {"history_rows": prune_history(root, now), "completed_logs": prune_logs(root, now)}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("root", nargs="?", default="/var/lib/calibre-web-automated")
  args = parser.parse_args()
  # Honor the systemd service's explicit TZ setting for local CWA history.
  if "TZ" in os.environ:
    time.tzset()
  print(json.dumps(retain(args.root), sort_keys=True))


if __name__ == "__main__":
  main()
