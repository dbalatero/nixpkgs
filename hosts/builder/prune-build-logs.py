"""Expire old Nix logs without rotating active writers or collecting store paths."""

from pathlib import Path
import stat
import time


def open_files():
  identities = set()
  for process in Path("/proc").iterdir():
    if not process.name.isdigit():
      continue
    try:
      for descriptor in (process / "fd").iterdir():
        try:
          info = descriptor.stat()
          identities.add((info.st_dev, info.st_ino))
        except FileNotFoundError:
          pass  # The descriptor closed during inspection.
    except (FileNotFoundError, ProcessLookupError):
      pass  # The process exited during inspection.
  # Permission errors deliberately abort before anything is deleted: an
  # incomplete /proc view cannot establish which logs are still in use.
  return identities


def prune(directory, *, now=None):
  cutoff = (time.time() if now is None else now) - 30 * 86400
  candidates = []
  for path in directory.glob("*/*"):
    if path.parent.is_symlink() or not path.name.endswith((".drv", ".drv.bz2")):
      continue
    try:
      info = path.lstat()
    except FileNotFoundError:
      continue
    if stat.S_ISREG(info.st_mode) and info.st_mtime < cutoff:
      candidates.append((path, info))
  active = open_files() if candidates else set()
  removed = 0
  for path, before in candidates:
    if (before.st_dev, before.st_ino) in active:
      continue
    try:
      after = path.lstat()
      # Skip logs replaced or touched while collecting the open-file snapshot.
      if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
      ):
        continue
      path.unlink()
      removed += 1
    except FileNotFoundError:
      pass
  print(f"Removed {removed} inactive Nix build logs older than 30 days")
  return removed


if __name__ == "__main__":
  prune(Path("/nix/var/log/nix/drvs"))
