"""Durable inventory and append-only review history (standard library only)."""
import csv
import hashlib
import json
import os
import sqlite3
import stat
import time
from pathlib import Path


def packed(value):
  return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def digest(value):
  return hashlib.sha256(packed(value).encode()).hexdigest()


def signature(path):
  s = Path(path).lstat()
  if not stat.S_ISREG(s.st_mode):
    raise ValueError(f"Not a regular file: {path}")
  return [s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_dev, s.st_ino]


def checksum(path):
  before = signature(path)
  h = hashlib.sha256()
  with open(path, "rb") as stream:
    for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
      h.update(block)
  if signature(path) != before:
    raise ValueError(f"File changed while hashing: {path}")
  return h.hexdigest()


def contained(root, relative):
  root = Path(root).resolve()
  rel = Path(relative)
  if rel.is_absolute() or ".." in rel.parts or not rel.parts:
    raise ValueError(f"Unsafe relative path: {relative}")
  path = root / rel
  # Reject even in-root symlinks: reviewed path semantics must be literal.
  current = root
  for part in rel.parts:
    current /= part
    if current.is_symlink():
      raise ValueError(f"Symlink in media path: {current}")
  if not path.resolve().is_relative_to(root):
    raise ValueError(f"Path escapes root: {relative}")
  return path


def classify(relative):
  p = Path(relative)
  ext = p.suffix.lower()
  low = relative.lower()
  if any(part.startswith(".rsync-partial") for part in p.parts) or ext in {".part", ".partial", ".!qb", ".tmp"}:
    return "partial"
  if ext in {".rar", ".zip", ".7z", ".gz", ".tar"} or (len(ext) == 4 and ext[1] == "r" and ext[2:].isdigit()):
    return "archive"
  if ext in {".mkv", ".avi", ".mp4", ".mov", ".mpg", ".mpeg", ".m4v", ".ts", ".webm"}:
    if "sample" in p.stem.lower():
      return "sample"
    return "tv" if p.parts[0] == "TV Shows" else "movie" if p.parts[0] == "Movies" else "video"
  if ext in {".flac", ".mp3", ".m4a", ".m4b", ".ogg", ".opus", ".wav", ".aac", ".aiff", ".ape"}:
    if "hardcore history" in low:
      return "spoken-word"
    return "audiobook" if p.parts[0] in {"Books", "Audio"} or ext == ".m4b" else "music"
  if ext in {".srt", ".sub", ".idx", ".ass", ".ssa", ".jpg", ".jpeg", ".png", ".cue", ".log", ".m3u", ".m3u8", ".nfo", ".txt", ".sfv", ".srr", ".lrc"}:
    return "companion"
  return "other"


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scans (
  id INTEGER PRIMARY KEY, started REAL NOT NULL, finished REAL, errors TEXT
);
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
  current_revision INTEGER, present INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS revisions (
  id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL REFERENCES files(id),
  signature TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL,
  observations INTEGER NOT NULL DEFAULT 1, probe TEXT
);
CREATE TABLE IF NOT EXISTS proposals (
  id INTEGER PRIMARY KEY, revision_id INTEGER NOT NULL REFERENCES revisions(id),
  mapping TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY, revision_id INTEGER NOT NULL REFERENCES revisions(id),
  proposal_id INTEGER REFERENCES proposals(id), action TEXT NOT NULL,
  reason TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS batches (
  id INTEGER PRIMARY KEY, manifest TEXT NOT NULL, digest TEXT NOT NULL,
  approved REAL NOT NULL, transfer_confirmed REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS operations (
  id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES batches(id),
  proposal_id INTEGER UNIQUE NOT NULL REFERENCES proposals(id), status TEXT NOT NULL,
  before_hash TEXT, verified_signature TEXT, app_record TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, created REAL NOT NULL, category TEXT NOT NULL,
  file_id INTEGER, detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS revisions_file ON revisions(file_id);
CREATE INDEX IF NOT EXISTS proposals_revision ON proposals(revision_id);
CREATE INDEX IF NOT EXISTS decisions_revision ON decisions(revision_id);
CREATE INDEX IF NOT EXISTS operations_batch ON operations(batch_id);
"""


class Store:
  def __init__(self, path, root):
    self.path = Path(path)
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self.db = sqlite3.connect(self.path)
    self.db.row_factory = sqlite3.Row
    self.db.execute("PRAGMA foreign_keys=ON")
    self.db.execute("PRAGMA journal_mode=WAL")
    self.db.executescript(SCHEMA)
    version = self.db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
    if version and version[0] != "1":
      raise ValueError("Unsupported audit database version")
    previous = self.db.execute("SELECT value FROM meta WHERE key='source_root'").fetchone()
    source_root = os.path.abspath(root)
    if previous and previous[0] != source_root:
      raise ValueError("Database belongs to a different source root")
    self.db.execute("INSERT OR IGNORE INTO meta VALUES ('schema', '1')")
    self.db.execute("INSERT OR IGNORE INTO meta VALUES ('source_root', ?)", (source_root,))
    self.db.commit()
    self.root = Path(source_root)

  def event(self, category, detail, file_id=None):
    self.db.execute("INSERT INTO events(created,category,file_id,detail) VALUES (?,?,?,?)",
      (time.time(), category, file_id, packed(detail)))

  def backup(self, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"audit-{time.time_ns()}.sqlite"
    self.db.commit()
    with sqlite3.connect(target) as other:
      self.db.backup(other)
    return target

  def inventory(self, now=None):
    now = time.time() if now is None else now
    if not self.root.is_dir():
      raise ValueError("Source root is unavailable")
    scan = self.db.execute("INSERT INTO scans(started) VALUES (?)", (now,)).lastrowid
    seen, errors = set(), []
    counts = {"new": 0, "changed": 0, "unchanged": 0, "missing": 0}

    def error(exc):
      errors.append(str(exc))

    for directory, dirs, names in os.walk(self.root, followlinks=False, onerror=error):
      # Symlink directories are explicitly recorded as errors, never traversed.
      for name in list(dirs):
        if (Path(directory) / name).is_symlink():
          errors.append(f"Symlink directory: {Path(directory) / name}")
          dirs.remove(name)
      for name in names:
        path = Path(directory) / name
        relative = str(path.relative_to(self.root))
        seen.add(relative)
        try:
          sig = packed(signature(path))
        except (OSError, ValueError) as exc:
          error(exc)
          continue
        row = self.db.execute("SELECT f.*, r.signature FROM files f LEFT JOIN revisions r ON r.id=f.current_revision WHERE path=?", (relative,)).fetchone()
        if row:
          expected = self.db.execute("SELECT verified_signature FROM operations o JOIN proposals p ON p.id=o.proposal_id WHERE p.revision_id=? AND o.verified_signature IS NOT NULL ORDER BY o.id DESC LIMIT 1", (row["current_revision"],)).fetchone()
          baseline = expected[0] if expected else row["signature"]
          if sig == baseline:
            self.db.execute("UPDATE revisions SET last_seen=?, observations=observations+1 WHERE id=?", (now, row["current_revision"]))
            self.db.execute("UPDATE files SET present=1 WHERE id=?", (row["id"],))
            if not row["present"]:
              self.event("source-returned", relative, row["id"])
            counts["unchanged"] += 1
            continue
          file_id = row["id"]
          counts["changed"] += 1
          self.event("source-changed", {"path": relative, "old": baseline, "new": sig}, file_id)
        else:
          file_id = self.db.execute("INSERT INTO files(path,kind) VALUES (?,?)", (relative, classify(relative))).lastrowid
          counts["new"] += 1
        revision = self.db.execute("INSERT INTO revisions(file_id,signature,first_seen,last_seen) VALUES (?,?,?,?)", (file_id, sig, now, now)).lastrowid
        self.db.execute("UPDATE files SET current_revision=?,present=1 WHERE id=?", (revision, file_id))
    if not errors:
      for row in self.db.execute("SELECT id,path FROM files WHERE present=1").fetchall():
        if row["path"] not in seen:
          self.db.execute("UPDATE files SET present=0 WHERE id=?", (row["id"],))
          self.event("source-missing", row["path"], row["id"])
          counts["missing"] += 1
    self.db.execute("UPDATE scans SET finished=?, errors=? WHERE id=?", (time.time(), packed(errors), scan))
    self.db.commit()
    return {**counts, "errors": errors, "scan": scan}

  def candidates(self, stability=600, retry=False):
    return self.db.execute("""
      SELECT f.*,r.id AS revision_id,r.signature,r.probe FROM files f
      JOIN revisions r ON r.id=f.current_revision
      WHERE present=1 AND r.observations>=2 AND r.last_seen-r.first_seen>=?
      AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.revision_id=r.id)
      AND (? OR NOT EXISTS (SELECT 1 FROM proposals p WHERE p.revision_id=r.id))
      AND NOT EXISTS (SELECT 1 FROM operations o JOIN proposals p ON p.id=o.proposal_id
        JOIN revisions old ON old.id=p.revision_id WHERE old.file_id=f.id)
      ORDER BY f.path
    """, (stability, retry)).fetchall()

  def propose(self, revision, mapping):
    proposal = self.db.execute("INSERT INTO proposals(revision_id,mapping,created) VALUES (?,?,?)", (revision, packed(mapping), time.time())).lastrowid
    self.db.commit()
    return proposal

  def decide(self, revision, action, reason, proposal=None):
    self.db.execute("INSERT INTO decisions(revision_id,proposal_id,action,reason,created) VALUES (?,?,?,?,?)", (revision, proposal, action, reason, time.time()))
    self.event("decision", {"revision": revision, "proposal": proposal, "action": action, "reason": reason})
    self.db.commit()

  def batch(self, proposals):
    manifest = []
    for proposal in proposals:
      row = self.db.execute("SELECT p.*,f.path,f.present,f.current_revision,r.signature FROM proposals p JOIN revisions r ON r.id=p.revision_id JOIN files f ON f.id=r.file_id WHERE p.id=?", (proposal,)).fetchone()
      decision = self.db.execute("SELECT action,proposal_id FROM decisions WHERE revision_id=? ORDER BY id DESC LIMIT 1", (row["revision_id"],)).fetchone() if row else None
      if not row or not row["present"] or row["revision_id"] != row["current_revision"] or not decision or decision["action"] != "accept" or decision["proposal_id"] != proposal:
        raise ValueError(f"Proposal {proposal} is not currently accepted")
      if self.db.execute("SELECT 1 FROM operations WHERE proposal_id=?", (proposal,)).fetchone():
        raise ValueError(f"Proposal {proposal} already belongs to a batch")
      mapping = json.loads(row["mapping"])
      if not mapping.get("destination") or not mapping.get("identity"):
        raise ValueError(f"Proposal {proposal} has unresolved mapping")
      manifest.append({"proposal": proposal, "revision": row["revision_id"], "source": row["path"], "signature": json.loads(row["signature"]), "mapping": mapping})
    if not manifest:
      raise ValueError("Empty batch")
    destinations = [m["mapping"]["destination"] for m in manifest]
    if len(set(destinations)) != len(destinations):
      raise ValueError("Batch has duplicate destinations")
    batch = self.db.execute("INSERT INTO batches(manifest,digest,approved,transfer_confirmed) VALUES (?,?,?,?)", (packed(manifest), digest(manifest), time.time(), time.time())).lastrowid
    for item in manifest:
      self.db.execute("INSERT INTO operations(batch_id,proposal_id,status) VALUES (?,?,'approved')", (batch, item["proposal"]))
    self.event("batch-approved", {"batch": batch, "digest": digest(manifest)})
    self.db.commit()
    return batch

  def export(self, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for table in ("files", "revisions", "proposals", "decisions", "batches", "operations", "events", "scans"):
      cursor = self.db.execute(f"SELECT * FROM {table}")
      with (directory / f"{table}.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([col[0] for col in cursor.description])
        writer.writerows(cursor)
    with (directory / "current.csv").open("w", newline="") as stream:
      fields = ["file_id", "source", "kind", "state", "destination", "identity", "reason", "sha256"]
      writer = csv.DictWriter(stream, fieldnames=fields)
      writer.writeheader()
      writer.writerows(self.report())

  def report(self):
    for row in self.db.execute("SELECT * FROM files ORDER BY path"):
      op = self.db.execute("""SELECT o.*,p.revision_id,p.mapping FROM operations o
        JOIN proposals p ON p.id=o.proposal_id JOIN revisions r ON r.id=p.revision_id
        WHERE r.file_id=? ORDER BY o.id DESC LIMIT 1""", (row["id"],)).fetchone()
      decision = self.db.execute("SELECT * FROM decisions WHERE revision_id=? ORDER BY id DESC LIMIT 1", (row["current_revision"],)).fetchone()
      proposal = self.db.execute("SELECT mapping FROM proposals WHERE revision_id=? ORDER BY id DESC LIMIT 1", (row["current_revision"],)).fetchone()
      mapping = json.loads(op["mapping"] if op else proposal[0]) if op or proposal else {}
      reason = op["error"] if op and op["error"] else decision["reason"] if decision else mapping.get("issue", "")
      if not row["present"]:
        state = "missing-source"
      elif op and op["revision_id"] != row["current_revision"]:
        state = "integrity-issue"
      elif op:
        state = "failed" if op["error"] else op["status"]
        if state == "verified" and mapping.get("alternate"):
          state = "verified-alternate"
        elif state == "verified" and mapping.get("kind") == "companion":
          state = "verified-companion"
      elif decision:
        state = decision["action"]
      elif proposal:
        state = "review"
      else:
        state = "pending"
      yield {"file_id": row["id"], "source": row["path"], "kind": row["kind"], "state": state,
        "destination": mapping.get("destination", ""), "identity": packed(mapping.get("identity", {})),
        "reason": reason, "sha256": op["before_hash"] if op else ""}
