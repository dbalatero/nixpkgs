"""Incremental migration CLI. All media writes require an approved manifest."""
import argparse
import collections
import concurrent.futures
import threading
from contextlib import contextmanager
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import termios
import tty
import time
import zipfile
from pathlib import Path

from .music_review import album_folder
from .apps import Apps
from .music_copy import is_copy, owned as owned_copy, copy_file, state as copy_state
from .store import prune_audit_snapshots, Store, checksum, contained, digest, packed, signature, validate_book_mappings


def mount_check(config):
  source = Path(config["source"])
  if not source.is_dir():
    raise ValueError("Torrent source directory is unavailable")
  mount = config["mount"]
  result = subprocess.run(["findmnt", "-J", "-T", str(source), "-o", "SOURCE,FSTYPE,TARGET"], check=True, capture_output=True, text=True)
  mounts = json.loads(result.stdout)["filesystems"]
  if not any(m["source"] == mount["source"] and m["fstype"] in {"nfs", "nfs4"} and m["target"] == mount["target"] for m in mounts):
    raise ValueError("Expected NAS mount is absent; refusing to scan or write")


@contextmanager
def audit_lock(path):
  with Path(path).open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
      yield
    finally:
      fcntl.flock(lock, fcntl.LOCK_UN)


class HashProgress:
  def __init__(self, total):
    self.total = total
    self.completed = 0
    self.read = 0
    self.offset = 0
    self.file_size = 0
    self.started = time.monotonic()
    self.last = self.started

  def update(self, offset, force=False):
    self.read += max(0, offset - self.offset)
    self.offset = offset
    now = time.monotonic()
    if not force and now - self.last < (1 if sys.stdout.isatty() else 10):
      return
    self.last = now
    elapsed = max(now - self.started, 0.001)
    speed = self.read / elapsed
    done = min(self.total, self.completed + offset)
    percent = 100 * done / self.total if self.total else 100
    file_percent = 100 * offset / self.file_size if self.file_size else 100
    eta = time.strftime("%H:%M:%S", time.gmtime((self.total - done) / speed)) if speed else "--:--:--"
    remaining_hours = (self.total - done) / speed / 3600 if speed else 0
    if remaining_hours >= 24:
      eta = f"{remaining_hours:.1f}h"
    text = f"Queue {percent:6.2f}% | file {file_percent:6.2f}% | {speed / 1024**2:.1f} MiB/s | ETA {eta}"
    print(("\r" if sys.stdout.isatty() else "") + text, end="" if sys.stdout.isatty() else "\n", flush=True)

  def finish_file(self, size):
    self.completed += size
    self.offset = 0
    self.file_size = 0
    self.update(0, force=True)
    if sys.stdout.isatty():
      print(flush=True)


def precompute_hashes(config, limit=None, kinds=None, files=None):
  """Hash outside the audit lock; revalidate under the lock before publishing."""
  db = Path(config["database"])
  db.parent.mkdir(parents=True, exist_ok=True)
  with (db.parent / "hash.lock").open("a") as worker:
    try:
      fcntl.flock(worker, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
      raise ValueError("A hash worker is already running") from None
    lock = db.parent / "audit.lock"
    with audit_lock(lock):
      store = Store(db, config["source"])
      rows = store.hash_candidates(config.get("stabilitySeconds", 600))
    counts = {"hashed": 0, "cached": 0, "skipped": 0, "errors": 0}
    try:
      selected = [r for r in rows if (not kinds or r["kind"] in kinds) and (not files or r["id"] in files)]
      if limit is not None:
        selected = selected[:limit]
      progress = HashProgress(sum(json.loads(r["signature"])[0] for r in selected))
      print(f"Checking {len(selected)} stable files; completed imports are excluded.", flush=True)
      for index, row in enumerate(selected, 1):
        mount_check(config)
        size = json.loads(row["signature"])[0]
        try:
          source = contained(store.root, row["path"])
          observed = signature(source)
          if observed != json.loads(row["signature"]):
            counts["skipped"] += 1
            print(f"Changed; run inventory again: {row['path']}", flush=True)
            continue
          if store.cached_hash(row["revision_id"], observed):
            counts["cached"] += 1
            continue
          print(f"[{index}/{len(selected)}] Hashing {observed[0] / 1024**3:.2f} GiB: {row['path']}", flush=True)
          started = time.monotonic()
          progress.file_size = size
          value = checksum(source, progress=progress.update)
          with audit_lock(lock):
            current = store.db.execute("SELECT current_revision,present FROM files WHERE id=?", (row["id"],)).fetchone()
            operated = store.db.execute("""SELECT 1 FROM operations o JOIN proposals p ON p.id=o.proposal_id
              JOIN revisions r ON r.id=p.revision_id WHERE r.file_id=?""", (row["id"],)).fetchone()
            if not current["present"] or current["current_revision"] != row["revision_id"] or operated or signature(source) != observed:
              counts["skipped"] += 1
              print("File or import state changed; discarded hash.", flush=True)
              continue
            store.save_hash(row["revision_id"], observed, value)
          counts["hashed"] += 1
          print(f"Cached in {time.monotonic() - started:.1f}s", flush=True)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
          counts["errors"] += 1
          print(f"Skipped {row['path']}: {exc}", flush=True)
        finally:
          progress.finish_file(size)
      print("Hash progress:", packed(counts), flush=True)
    finally:
      store.db.close()
    return counts


def clean(text):
  return re.sub(r'[\x00-\x1f/\\:*?"<>|]', "_", str(text)).strip().rstrip(".") or "Unknown"


def inspect_file(path, kind):
  if kind == "archive":
    if path.suffix.lower() == ".zip":
      with zipfile.ZipFile(path) as archive:
        return {"members": [{"path": x.filename, "bytes": x.file_size} for x in archive.infolist()], "extracted": False}
    if path.suffix.lower() == ".rar":
      result = subprocess.run(["7zz", "l", "-slt", "--", str(path)], capture_output=True, text=True, timeout=120)
      return {"listing": result.stdout, "returnCode": result.returncode, "extracted": False}
    return {"archive": "manual audit required", "extracted": False}
  if kind not in {"movie", "tv", "music", "audiobook", "spoken-word", "podcast", "video"}:
    return {}
  result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, timeout=120)
  if result.returncode:
    raise ValueError("ffprobe failed; file may be incomplete or unsupported")
  return json.loads(result.stdout)


def guess(path, probe):
  from guessit import guessit
  value = dict(guessit(str(path)))
  tags = {k.lower(): v for k, v in probe.get("format", {}).get("tags", {}).items()}
  for stream in probe.get("streams", []):
    tags.update({k.lower(): v for k, v in stream.get("tags", {}).items()})
  value["tags"] = tags
  # guessit can return date objects; persist a JSON-compatible snapshot.
  return json.loads(json.dumps(value, default=str))


def mapping_for(kind, source, candidate, evidence, version):
  title = candidate.get("title", "Unknown")
  year = candidate.get("year", str(candidate.get("releaseDate", ""))[:4])
  mapping = {"kind": kind, "identity": {}, "evidence": evidence, "appVersion": version}
  filename = Path(source).name
  if kind == "movie":
    folder = f"movies/{clean(title)} ({year}) {{tmdb-{candidate['tmdbId']}}}"
    mapping.update(identity={"title": title, "year": year, "tmdbId": candidate["tmdbId"]}, entityPath=folder, destination=f"{folder}/{filename}")
  elif kind == "tv":
    g = evidence["guess"]
    season = g.get("season")
    episode = g.get("episode")
    # Explicit SxxEyy tokens outrank numbers parsed from an episode title.
    explicit = re.search(r'(?i)(?<![a-z0-9])S(\d{1,4})E(\d{1,3})((?:E\d{1,3})*)(?!\d)', filename)
    if explicit and not re.match(r'[-–](?:[Ee])?\d', filename[explicit.end():]):
      season = int(explicit[1])
      episode = [int(explicit[2])] + [int(n) for n in re.findall(r'(?i)E(\d+)', explicit[3])]
    if isinstance(season, list) or not isinstance(season, int) or not episode:
      raise ValueError("Explicit season/episode mapping needed (specials/date/absolute numbering)")
    episodes = episode if isinstance(episode, list) else [episode]
    folder = f"tv/{clean(title)} ({year}) {{tvdb-{candidate['tvdbId']}}}"
    numbering = f"S{season:02d}" + "".join(f"E{e:02d}" for e in episodes)
    mapping.update(identity={"title": title, "tvdbId": candidate["tvdbId"]}, entityPath=folder, season=season, episodes=episodes, destination=f"{folder}/Season {season:02d}/{clean(title)} - {numbering} - {filename}")
  elif kind == "music":
    artist = candidate["artist"]
    tags = evidence["guess"]["tags"]
    disc = int(str(tags.get("disc", tags.get("discnumber", 1))).split("/")[0])
    track = int(str(tags.get("track", tags.get("tracknumber", ""))).split("/")[0])
    releases = candidate.get("releases", [])
    if not releases:
      raise ValueError("No MusicBrainz release available; explicit release selection needed")
    folder = f"music/{clean(artist['artistName'])}"
    mapping.update(identity={"title": title, "artist": artist["artistName"], "foreignArtistId": artist["foreignArtistId"], "foreignAlbumId": candidate["foreignAlbumId"], "foreignReleaseId": releases[0]["foreignReleaseId"]}, entityPath=folder, disc=disc, track=track, destination=f"{folder}/{clean(title)} ({year})/{disc:02d}-{track:02d} - {filename}")
    mapping["releaseChoices"] = [{k: r.get(k) for k in ("title", "foreignReleaseId", "trackCount", "format", "country", "disambiguation")} for r in releases]
  return mapping


def hardcore_history_mapping(source, evidence=None):
  path = Path(source)
  match = re.fullmatch(r"dchha(\d+)(?:\s*-\s*|_+)(.+)", path.stem, re.IGNORECASE)
  if not match:
    raise ValueError("Hardcore History episode number/title needs manual review")
  number, title = int(match[1]), re.sub(r"_+", " ", match[2]).strip()
  folder = f"podcasts/Dan Carlin/Hardcore History/{number:03d} - {clean(title)}"
  return {"kind": "podcast", "identity": {"title": title, "author": "Dan Carlin",
    "series": [{"name": "Hardcore History", "sequence": str(number)}]}, "order": 1,
    "entityPath": folder, "destination": f"{folder}/{path.name}", "evidence": evidence or {"source": str(source), "basis": "episode number and title from filename"}}


def propose(store, config, limit, kinds=None, files=None, retry=False):
  selected = []
  music_folders = set()
  for row in store.candidates(config.get("stabilitySeconds", 600), retry=retry):
    if (kinds and row["kind"] not in kinds) or (files and row["id"] not in files):
      continue
    folder = str(album_folder(row["path"]))
    if len(selected) >= limit and not (row["kind"] == "music" and folder in music_folders):
      continue
    if row["kind"] == "music":
      music_folders.add(folder)
    selected.append(dict(row))
  workers = min(config.get('prepWorkers', 16), max(1, len(selected)))
  if not 1 <= workers <= 64:
    raise ValueError('Preparation workers must be between 1 and 64')
  root = store.root
  lookup_lock = threading.Lock()
  lookup_slots = threading.Semaphore(4)
  lookups = {}
  for cached in store.db.execute('SELECT key,value FROM cache'):
    if cached['key'].split(':', 1)[0] in {'movie', 'tv', 'music'}:
      future = concurrent.futures.Future()
      future.set_result(json.loads(cached['value']))
      lookups[cached['key']] = future

  def prepare(row):
    path = contained(root, row["path"])
    evidence = {"source": row["path"], "classification": row["kind"]}
    options, issue = [], ""
    try:
      if signature(path) != json.loads(row["signature"]):
        raise ValueError("Source changed; inventory again")
      probe = json.loads(row["probe"]) if row["probe"] else inspect_file(path, row["kind"])
      if signature(path) != json.loads(row["signature"]):
        raise ValueError("Source changed during inspection")

      evidence["probe"] = probe
      if row["kind"] in {"movie", "tv", "music"}:
        parsed = guess(Path(row["path"]), probe)
        evidence["guess"] = parsed
        query = str(parsed.get("title", Path(row["path"]).stem))
        if row["kind"] == "movie" and parsed.get("year"):
          query += " " + str(parsed["year"])
        if row["kind"] == "music":
          tags = parsed["tags"]
          query = str(tags.get("albumartist", tags.get("artist", ""))) + " " + str(tags.get("album", ""))
        key = row["kind"] + ":" + query
        with lookup_lock:
          future = lookups.get(key)
          owner = future is None
          if owner:
            future = concurrent.futures.Future()
            lookups[key] = future
        if owner:
          try:
            with lookup_slots:
              future.set_result(Apps(config).lookup(row["kind"], query))
          except Exception as exc:
            future.set_exception(exc)
        lookup = future.result()
        evidence["query"] = query
        evidence["candidates"] = lookup["results"]
        for candidate in lookup["results"][:10]:
          try:
            options.append(mapping_for(row["kind"], row["path"], candidate, evidence, lookup["version"]))
          except (KeyError, ValueError, TypeError) as exc:
            issue = str(exc)
        if len(options) != 1:
          issue = issue or f"{len(options)} candidate mappings; select an identity"
      elif row["kind"] in {"audiobook", "spoken-word", "podcast"}:
        tags = guess(Path(row["path"]), probe)["tags"]
        title = tags.get("album", "")
        author = tags.get("albumartist", tags.get("artist", ""))
        if row["kind"] in {"spoken-word", "podcast"} and "hardcore history" in row["path"].lower():
          options = [hardcore_history_mapping(row["path"], evidence)]
        elif title and author:
          folder = ({"spoken-word": "spoken-word", "podcast": "podcasts"}.get(row["kind"], "audiobooks")) + f"/{clean(author)}/{clean(title)}"
          order = int(str(tags.get("track", tags.get("tracknumber", 1))).split("/")[0])
          options = [{"kind": row["kind"], "identity": {"title": title, "author": author}, "order": order, "destination": f"{folder}/{path.name}", "entityPath": folder, "evidence": evidence}]
        issue = "Confirm book/collection identity and multipart order from tags"
      else:
        issue = {"archive": "Hand audit archive; extraction is disabled", "partial": "Incomplete/temporary transfer; never import", "companion": "Assign to an approved parent release or explicitly retain at source", "sample": "Confirm sample exclusion", "other": "Classify non-media or deferred category", "video": "Video outside movie/TV categories; explicit classification needed"}.get(row["kind"], "Manual classification needed")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
      issue = str(exc)
    return {"kind": row["kind"], "options": options, "issue": issue, "evidence": evidence}

  count = 0
  total = len(selected)
  started = time.monotonic()
  last_progress = 0
  def progress(force=False):
    nonlocal last_progress
    now = time.monotonic()
    if not force and now - last_progress < (1 if sys.stdout.isatty() else 5):
      return
    last_progress = now
    elapsed = now - started
    message = f'Preparing review: {count}/{total} ({count / total * 100 if total else 100:.0f}%) | {workers} workers | {elapsed:.0f}s elapsed'
    print(('\r\033[K' if sys.stdout.isatty() else '') + message,
      end='' if sys.stdout.isatty() else '\n', flush=True)
  progress(True)
  executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
  pending = {executor.submit(prepare, row): row for row in selected}
  try:
    while pending:
      done, _ = concurrent.futures.wait(pending, timeout=0.25, return_when=concurrent.futures.FIRST_COMPLETED)
      for future in done:
        row = pending.pop(future)
        mapping = future.result()
        evidence = mapping['evidence']
        # Only this main thread writes SQLite; completed work is saved immediately.
        if 'probe' in evidence:
          store.db.execute('UPDATE revisions SET probe=? WHERE id=?', (packed(evidence['probe']), row['revision_id']))
        if 'query' in evidence:
          key = row['kind'] + ':' + evidence['query']
          lookup = lookups[key].result()
          store.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (key, packed(lookup), time.time()))
        store.propose(row['revision_id'], mapping)
        count += 1
      progress()
  finally:
    executor.shutdown(wait=True, cancel_futures=True)
    progress(True)
    if sys.stdout.isatty():
      print()
  print(f"Created {count} review records. Nothing imported.")


def validate_mapping(mapping, config):
  for key in ("kind", "identity", "destination", "entityPath"):
    if not mapping.get(key):
      raise ValueError(f"Missing mapping field: {key}")
  kind = mapping["kind"]
  root = {"movie": "movies", "tv": "tv", "music": "music", "audiobook": "audiobooks", "spoken-word": "spoken-word", "podcast": "podcasts", "companion": None}.get(kind)
  if kind not in {"movie", "tv", "music", "audiobook", "spoken-word", "podcast", "companion"}:
    raise ValueError("Unsupported media kind; archives cannot be imported")
  path = contained(config["media"], mapping["destination"])
  entity = contained(config["media"], mapping["entityPath"])
  if not path.is_relative_to(entity) or path == entity:
    raise ValueError("Destination must be inside its entity directory")
  if mapping.get("alternate"):
    if Path(mapping["destination"]).parts[0] != "alternates":
      raise ValueError("Alternates must be outside managed app roots")
  elif root and Path(mapping["destination"]).parts[0] != root:
    raise ValueError("Incorrect destination root for media kind")
  if kind == "tv" and (not isinstance(mapping.get("season"), int) or not mapping.get("episodes")):
    raise ValueError("TV requires explicit season and episodes")
  if kind == "music" and not all(mapping.get(x) for x in ("disc", "track")):
    raise ValueError("Music requires explicit disc and track")
  if kind in {"audiobook", "spoken-word", "podcast"} and (not isinstance(mapping.get("order"), int) or mapping["order"] < 1 or not mapping["identity"].get("author")):
    raise ValueError("Audiobooks require an author and explicit 1-based file order")
  return path


def edit_mapping(mapping):
  with tempfile.TemporaryDirectory(prefix="media-review-") as temp:
    path = Path(temp) / "mapping.json"
    path.write_text(json.dumps(mapping, indent=2) + "\n")
    subprocess.run(shlex.split(os.environ.get("EDITOR", "vi")) + [str(path)], check=True)
    return json.loads(path.read_text())


def key_choice(prompt, choices, default=None):
  """Single-key terminal input, with a line-input fallback for redirected stdin."""
  while True:
    if sys.stdin.isatty():
      print(prompt, end="", flush=True)
      fd = sys.stdin.fileno()
      old = termios.tcgetattr(fd)
      try:
        tty.setcbreak(fd)
        value = sys.stdin.read(1).lower()
      finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
      print()
    else:
      value = input(prompt).strip().lower()
    if value in {"\r", "\n", ""}:
      value = default
    if value in choices:
      return value
    print("Choose " + "/".join(choices) + ".")


def review_rows(store, ids=None, kinds=None, limit=None):
  rows = store.db.execute("""SELECT p.*,f.path,f.kind,f.id AS file_id FROM proposals p
    JOIN revisions r ON r.id=p.revision_id JOIN files f ON f.current_revision=r.id
    WHERE f.present=1 AND p.id=(SELECT MAX(p2.id) FROM proposals p2 WHERE p2.revision_id=r.id)
    AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.revision_id=r.id)
    AND NOT EXISTS (SELECT 1 FROM operations o JOIN proposals old ON old.id=o.proposal_id
      JOIN revisions oldr ON oldr.id=old.revision_id WHERE oldr.file_id=f.id)
    ORDER BY f.path""").fetchall()
  filtered = [{**dict(r), "mapping": packed(store.relocate_mapping(json.loads(r["mapping"])))} for r in rows
    if (not ids or r["file_id"] in ids) and (not kinds or r["kind"] in kinds)]
  selected = filtered[:limit]
  folders = {album_folder(r['path']) for r in selected if r['kind'] == 'music'}
  selected_ids = {r['id'] for r in selected}
  return [r for r in filtered if r['id'] in selected_ids or (r['kind'] == 'music' and album_folder(r['path']) in folders)]


def show_mapping(mapping):
  if mapping['kind'] == 'music':
    identity = mapping['identity']
    print(f"  Match: {identity['artist']} — {identity['title']}")
    if mapping.get('expectedTrack'):
      print(f"  Track: {mapping['expectedTrack']['title']}")
    if mapping.get('releaseEvidence'):
      from .music_review import release_label
      print('  Edition:', release_label(mapping['releaseEvidence']))
  else:
    print("  Match:", packed(mapping["identity"]))
  assignment = {k: mapping[k] for k in ("season", "episodes", "disc", "track", "order") if k in mapping}
  if assignment:
    print("  Assignment:", packed(assignment))
  print("  Library:", mapping["destination"])


def same_tv_source(left, right):
  """A shared search candidate is not evidence that files belong to one show."""
  def source_key(mapping):
    evidence = mapping.get('evidence', {})
    title = evidence.get('guess', {}).get('title')
    if title:
      return ('title', re.sub(r'[^\w]', '', str(title).casefold()))
    source = evidence.get('source')
    return ('folder', str(Path(source).parent)) if source else None
  key = source_key(left)
  return key is not None and key == source_key(right)


def review(store, config, ids=None, kinds=None, limit=None):
  rows = review_rows(store, ids, kinds, limit)
  accepted, handled = [], set()
  for index, row in enumerate(rows, 1):
    if row["revision_id"] in handled:
      continue
    if row['kind'] == 'music':
      from .music_review import review_album
      group = [r for r in rows if r['kind'] == 'music' and album_folder(r['path']) == album_folder(row['path']) and r['revision_id'] not in handled]
      result = review_album(store, config, group, key_choice, Apps(config))
      handled.update(r['revision_id'] for r in group)
      if result == 'i':
        return True
      if result == 'q':
        print('Selections saved; nothing imported.')
        return False
      continue
    proposal = json.loads(row["mapping"])
    print(f"\n[{index}/{len(rows)}] {row['kind']} | {row['path']}")
    if proposal.get("issue"):
      print(proposal["issue"])
    options = proposal.get("options", [proposal] if proposal.get("destination") else [])[:10]
    keys = {str(i % 10): option for i, option in enumerate(options, 1)}
    for key, option in keys.items():
      print(f"  [{key}] {packed(option['identity'])}\n      → {option['destination']}")
    default = "1" if len(options) == 1 else None
    prompt = ("Enter=only match; " if default else "Number=match; ") + "v=details, e=edit, d=defer, x=exclude, i=import selected, q=save/quit: "
    answer = key_choice(prompt, list(keys) + ["v", "e", "d", "x", "i", "q"], default)
    while answer == "v":
      print(json.dumps(proposal.get("evidence", proposal), indent=2))
      answer = key_choice(prompt, list(keys) + ["v", "e", "d", "x", "i", "q"], default)
    if answer == "q":
      print("Selections saved. Run media-import again to continue; nothing imported.")
      return False
    if answer == "i":
      return True
    if answer in {"x", "d"}:
      reason = "Excluded in terminal review" if answer == "x" else "Needs further review"
      store.decide(row["revision_id"], "exclude" if answer == "x" else "defer", reason, row["id"])
      continue
    mapping = edit_mapping(keys.get("1", {"kind": row["kind"], "identity": {}, "entityPath": "", "destination": ""})) if answer == "e" else keys[answer]
    if mapping.get("releaseChoices"):
      for i, release in enumerate(mapping["releaseChoices"], 1):
        print(i, packed(release))
      choice = input("Music release number, then Enter (blank skips): ").strip()
      if not choice.isdigit() or not 1 <= int(choice) <= len(mapping["releaseChoices"]):
        continue
      mapping["identity"]["foreignReleaseId"] = mapping["releaseChoices"][int(choice) - 1]["foreignReleaseId"]
    validate_mapping(mapping, config)
    show_mapping(mapping)
    answer = key_choice("Enter=keep, g=group preview, a=alternate, s=skip, q=save/quit: ", ["y", "g", "a", "s", "q"], "y")
    if answer == "q":
      return False
    if answer == "s":
      continue
    if answer == "a":
      mapping["entityPath"] = "alternates/" + mapping["entityPath"]
      mapping["destination"] = "alternates/" + mapping["destination"]
      mapping["alternate"] = True
      validate_mapping(mapping, config)
      show_mapping(mapping)
      if key_choice("Keep this alternate? [y/N]: ", ["y", "n"], "n") != "y":
        continue
    group = [(row, mapping)]
    if answer == "g":
      if mapping["kind"] not in {"tv", "music", "audiobook", "spoken-word", "podcast"}:
        print("Groups are for seasons, albums, and multipart books.")
        continue
      group = []
      for other in rows:
        if other["revision_id"] in handled:
          continue
        data = json.loads(other["mapping"])
        options = [mapping] if other["id"] == row["id"] else data.get("options", [data] if data.get("destination") else [])
        for option in options:
          if option.get("kind") != mapping["kind"] or option.get("entityPath") != mapping["entityPath"]:
            continue
          if mapping["kind"] == "tv":
            if option.get("season") != mapping["season"]:
              continue
            if other["id"] != row["id"] and not same_tv_source(mapping, option):
              continue
          if mapping["kind"] == "music":
            if option["identity"].get("foreignAlbumId") != mapping["identity"]["foreignAlbumId"]:
              continue
            option["identity"]["foreignReleaseId"] = mapping["identity"]["foreignReleaseId"]
          validate_mapping(option, config)
          group.append((other, option))
          break
      print(f"Group preview: {len(group)} files from this review queue")
      for other, option in group:
        print(other["path"])
        show_mapping(option)
      if key_choice("Keep this group? [y/N]: ", ["y", "n"], "n") != "y":
        continue
    for other, option in group:
      new_id = store.propose(other["revision_id"], option)
      store.decide(other["revision_id"], "accept", "Accepted terminal mapping preview", new_id)
      accepted.append(new_id)
      handled.add(other["revision_id"])
    print(f"Saved. {len(accepted)} selected this session.")
  return True


def pending_proposals(store, ids=None, kinds=None):
  rows = store.db.execute("""SELECT p.id,f.id AS file_id,f.kind FROM proposals p
    JOIN decisions d ON d.proposal_id=p.id JOIN revisions r ON r.id=p.revision_id
    JOIN files f ON f.current_revision=r.id
    WHERE d.action='accept' AND f.present=1
    AND d.id=(SELECT MAX(d2.id) FROM decisions d2 WHERE d2.revision_id=r.id)
    AND NOT EXISTS (SELECT 1 FROM operations o JOIN proposals old ON old.id=o.proposal_id
      JOIN revisions oldr ON oldr.id=old.revision_id WHERE oldr.file_id=f.id)
    ORDER BY p.id""").fetchall()
  return [r["id"] for r in rows if (not ids or r["file_id"] in ids) and (not kinds or r["kind"] in kinds)]


def approve_batch(store, config, proposals, importing=False, background=False):
  if not proposals:
    print("No saved selections waiting to import.")
    return None
  print(f"\n{'Import' if importing else 'Approve'} preview: {len(proposals)} files (includes saved selections)")
  for proposal in proposals:
    row = store.db.execute("SELECT p.mapping,f.path FROM proposals p JOIN revisions r ON r.id=p.revision_id JOIN files f ON f.id=r.file_id WHERE p.id=?", (proposal,)).fetchone()
    if not row:
      raise ValueError(f"Unknown proposal {proposal}")
    mapping = store.relocate_mapping(json.loads(row["mapping"]))
    validate_mapping(mapping, config)
    print(row["path"])
    show_mapping(mapping)
  action = "Queue import" if background else ("Import and verify" if importing else "Approve batch")
  if key_choice(f"{action} these files, confirming their transfers are finished? [y/N]: ", ["y", "n"], "n") != "y":
    print("Selections saved; nothing imported.")
    return None
  mount_check(config)
  batch = store.batch(proposals)
  store.backup(config["localBackups"])
  return batch


def apply_batch(store, config, batch):
  row = store.db.execute("SELECT manifest FROM batches WHERE id=?", (batch,)).fetchone()
  if not row:
    raise ValueError("Unknown batch")
  if not store.db.execute("SELECT 1 FROM operations WHERE batch_id=? AND status NOT IN ('verified','superseded')", (batch,)).fetchone():
    print("Batch already verified; no operations performed.")
    return
  store.backup(config["localBackups"])
  manifest = json.loads(row[0])
  names = {{"movie": "radarr", "tv": "sonarr", "music": "lidarr"}.get(x["mapping"]["kind"]) for x in manifest}
  for name in sorted(n for n in names if n):
    Apps(config).api(name).command("Backup")
  if any(x["mapping"]["kind"] in {"audiobook", "spoken-word", "podcast"} for x in manifest):
    Apps(config).api("audiobookshelf").call("backups", "POST", {})
  print(f"Importing batch {batch}…", flush=True)
  try:
    execute(store, config, batch)
  except Exception:
    print(f"Progress saved. After resolving the error, resume with: media-import apply {batch}")
    raise
  print("Import complete. Library files and app assignments verified.")


def submit_batch(store, config, batch, kinds):
  if config.get('musicBackground') and kinds == ['music']:
    from .queue import enqueue
    enqueue(store, batch)
  else:
    apply_batch(store, config, batch)


def interactive_import(store, config, args):
  ids, kinds = args.files, args.kind
  from .queue import show as show_queue
  show_queue(store)
  unfinished = store.db.execute("SELECT DISTINCT batch_id FROM operations WHERE status NOT IN ('verified','superseded') AND batch_id NOT IN (SELECT batch_id FROM import_jobs)").fetchall()
  for row in unfinished:
    print(f"Unfinished batch {row[0]}: resume separately with media-import apply {row[0]}")
  if args.command == "run":
    print("Refreshing inventory…", flush=True)
    result = store.inventory()
    print(f"{result['new']} new, {result['changed']} changed, {result['missing']} missing.")
    if result["errors"]:
      raise ValueError("Incomplete inventory: " + packed(result["errors"]))
    print("New files need two observations at least ten minutes apart before review.")
    ready = review_rows(store, ids, kinds, args.limit)
    if len(ready) < args.limit:
      propose(store, config, args.limit - len(ready), kinds, ids)
    # Complete folders already partly prepared by earlier versions/limited queues.
    ready = review_rows(store, ids, kinds, args.limit)
    folders = {album_folder(r['path']) for r in ready if r['kind'] == 'music'}
    extra = [r['id'] for r in store.candidates(config.get('stabilitySeconds', 600))
      if r['kind'] == 'music' and album_folder(r['path']) in folders and (not ids or r['id'] in ids)]
    if extra:
      propose(store, config, len(extra), ['music'], extra)
  pending = pending_proposals(store, ids, kinds)
  if pending:
    print(f"{len(pending)} saved selections are waiting to import.")
    action = key_choice("Review more, import saved, or quit? [r/i/q, Enter=r]: ", ["r", "i", "q"], "r")
    if action == "q":
      return
    if action == "i":
      batch = approve_batch(store, config, pending, importing=True, background=bool(config.get('musicBackground') and kinds == ['music']))
      if batch:
        submit_batch(store, config, batch, kinds)
      return
  if review(store, config, ids, kinds, args.limit):
    batch = approve_batch(store, config, pending_proposals(store, ids, kinds), importing=True, background=bool(config.get('musicBackground') and kinds == ['music']))
    if batch:
      submit_batch(store, config, batch, kinds)


def preflight_item(store, config, item, op, allow_music_link=False):
  mapping = item["mapping"]
  destination = validate_mapping(mapping, config)
  source = contained(store.root, item["source"])
  current = store.db.execute("SELECT f.current_revision,f.present,f.kind FROM revisions r JOIN files f ON f.id=r.file_id WHERE r.id=?", (item["revision"],)).fetchone()
  if not current or not current["present"] or current["current_revision"] != item["revision"]:
    raise ValueError("Approval is stale: source revision changed or disappeared")
  if current["kind"] in {"archive", "partial"}:
    raise ValueError("Archives and partial transfers cannot be imported")
  decision = store.db.execute("SELECT action,proposal_id FROM decisions WHERE revision_id=? ORDER BY id DESC LIMIT 1", (item["revision"],)).fetchone()
  if not decision or decision["action"] != "accept" or decision["proposal_id"] != item["proposal"]:
    raise ValueError("Approval revoked or mapping superseded")
  expected = json.loads(op["verified_signature"]) if op["verified_signature"] else item["signature"]
  sig = signature(source)
  # A crash immediately after link() changes ctime but not content. Recover only
  # when preparation was recorded and size, mtime, device, and inode agree.
  recovering_link = op["status"] == "prepared" and op["app_record"] and destination.exists() and os.path.samefile(source, destination)
  if sig != expected and not (recovering_link and sig[:2] == expected[:2] and sig[3:] == expected[3:]):
    raise ValueError("Source changed since approval; do not import")
  if is_copy(mapping) and not allow_music_link:
    if destination.exists():
      saved = copy_state(store, op['id'])
      if saved and saved['phase'] == 'ready':
        # Publication may have completed immediately before a crash. copy_file
        # validates the saved inode and content hash before accepting it.
        pass
      else:
        owned_copy(store, op['id'], source, destination)
  elif destination.exists() and not os.path.samefile(source, destination):
    raise ValueError(f"Destination collision: {destination}")
  return source, destination


def execute(store, config, batch_id, apps=None, verify_only=False, verify_hashes=False):
  apps = Apps(config) if apps is None else apps
  batch = store.db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
  if not batch:
    raise ValueError("Unknown batch")
  manifest = json.loads(batch["manifest"])
  if digest(manifest) != batch["digest"]:
    raise ValueError("Manifest digest mismatch")
  manifest = [item for item in manifest if store.db.execute(
    "SELECT status FROM operations WHERE proposal_id=?", (item["proposal"],)).fetchone()[0] != "superseded"]
  manifest = [{**item, "mapping": store.relocate_mapping(item["mapping"])} for item in manifest]
  validate_book_mappings(manifest)
  media = Path(config["media"])
  # Preflight the complete batch before changing any library entry.
  for item in manifest:
    op = store.db.execute("SELECT * FROM operations WHERE proposal_id=?", (item["proposal"],)).fetchone()
    if op["status"] != "verified" or verify_only:
      preflight_item(store, config, item, op)
  handled_music = set()
  for item in manifest:
    if is_copy(item['mapping']) and not item['mapping'].get('alternate') and not verify_only and not verify_hashes and hasattr(apps, 'scan_music'):
      from .music_batch import album_key, execute_album
      key = album_key(item)
      if key not in handled_music:
        group = [entry for entry in manifest if is_copy(entry['mapping']) and not entry['mapping'].get('alternate') and album_key(entry) == key]
        execute_album(store, config, group, apps)
        handled_music.add(key)
      continue
    op = store.db.execute("SELECT * FROM operations WHERE proposal_id=?", (item["proposal"],)).fetchone()
    if op["status"] == "verified" and not verify_only:
      continue
    try:
      source, destination = preflight_item(store, config, item, op)
      observed = signature(source)
      before = op["before_hash"] or store.cached_hash(item["revision"], observed)
      if verify_hashes:
        actual = checksum(source)
        if before and actual != before:
          raise ValueError("Source hash differs from the saved baseline")
        if not before:
          print(f"Recording first content baseline (no prior hash): {item['source']}")
        before = actual
      if before and not op["before_hash"]:
        store.db.execute("UPDATE operations SET before_hash=? WHERE id=?", (before, op["id"]))
        store.db.commit()
      if signature(source) != observed:
        raise ValueError("Source changed before app preparation")
      record = store.relocate_record(json.loads(op["app_record"]), media) if op["app_record"] else None
      if not verify_only:
        before_prepare = signature(source)
        if record is None:
          record = apps.prepare(item["mapping"], media)
          if any(path != str(destination) for path in record.get("existingPaths", [])):
            raise ValueError("App already has a file for this identity; replacement is prohibited")
          store.db.execute("UPDATE operations SET app_record=?,status='prepared' WHERE id=?", (packed(record), op["id"]))
          store.db.commit()
        if signature(source) != before_prepare:
          raise ValueError("Source changed during app preparation")
        if is_copy(item['mapping']):
          copy_file(store, op['id'], source, destination)
        elif not destination.exists():
          old_umask = os.umask(0o007)
          try:
            destination.parent.mkdir(parents=True, exist_ok=True)
          finally:
            os.umask(old_umask)
          # No fallback copy, rename, unlink, chmod, or tag modification.
          os.link(source, destination, follow_symlinks=False)
        if is_copy(item['mapping']):
          owned_copy(store, op['id'], source, destination)
        elif not os.path.samefile(source, destination):
          raise ValueError("Destination is not a hardlink")
        linked_signature = signature(source)
        if linked_signature[:2] != observed[:2] or linked_signature[3:] != observed[3:]:
          raise ValueError("Source content changed while linking")
        observed = linked_signature
        store.db.execute("UPDATE operations SET status='linked',verified_signature=? WHERE id=?", (packed(signature(source)), op["id"]))
        store.db.commit()
        if record.get("app") in {"audiobookshelf", "lidarr"}:
          record["expectedPath"] = str(destination)
        apps.scan(record)
      if record is None or not destination.exists():
        raise ValueError("Missing app record or library file")
      if is_copy(item['mapping']):
        owned_copy(store, op['id'], source, destination)
      elif not os.path.samefile(source, destination):
        raise ValueError('Missing verified hardlink')
      record = apps.verify(record, item["mapping"], destination)
      if signature(source) != observed:
        raise ValueError("Source content changed during import; stop and investigate")
      if is_copy(item['mapping']):
        owned_copy(store, op['id'], source, destination)
      elif not os.path.samefile(source, destination):
        raise ValueError("App replaced the hardlink")
      store.db.execute("UPDATE operations SET status='verified',verified_signature=?,app_record=?,error=NULL WHERE id=?", (packed(signature(source)), packed(record), op["id"]))
      if before:
        store.save_hash(item["revision"], observed, before)
      store.event("verified", {"operation": op["id"], "sha256": before, "content_checked": verify_hashes, "destination": str(destination)})
      store.db.commit()
      print(f"Verified: {item['source']} -> {destination}", flush=True)
    except Exception as exc:
      store.db.execute("UPDATE operations SET error=? WHERE id=?", (str(exc), op["id"]))
      store.event("operation-failed", {"operation": op["id"], "error": str(exc)})
      store.db.commit()
      raise


def status(store):
  counts = collections.Counter()
  for row in store.report():
    counts[(row["kind"], row["state"])] += 1
  color = sys.stdout.isatty() and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb'
  for (kind, state), number in sorted(counts.items()):
    label = state
    if color:
      if state.startswith('verified') or state in {'exclude', 'superseded'}:
        code = 32
      elif state == 'defer':
        code = 33
      elif state in {'failed', 'integrity-issue', 'missing-source'}:
        code = 31
      else:
        code = 34
      label = f"\033[{code}m{state}\033[0m"
    print(f"{number:7d}  {kind:14s} {label}")
  last = store.db.execute("SELECT id,errors FROM scans ORDER BY id DESC LIMIT 1").fetchone()
  if last and json.loads(last["errors"]):
    print("LAST SCAN INCOMPLETE:", last["errors"])


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--config", default="/etc/media-import.json")
  parser.set_defaults(command="run", files=None, kind=None, limit=10)
  sub = parser.add_subparsers(dest="command")
  p = sub.add_parser("run", help="Refresh inventory, review matches, and import in one session")
  p.add_argument("--files", type=int, nargs="+")
  p.add_argument("--kind", nargs="+", default=["movie", "tv", "music", "audiobook", "spoken-word", "podcast"])
  p.add_argument("--limit", type=int, default=10)
  for name in ("inventory", "status", "configure", "backup", "queue", "work-queue"):
    sub.add_parser(name)
  p = sub.add_parser("hash", help="Precompute resumable SHA-256 hashes without importing")
  p.add_argument("--limit", type=int, help="Maximum number of stable files to check this run")
  p.add_argument("--kind", nargs="+")
  p.add_argument("--files", type=int, nargs="+")
  p = sub.add_parser("propose")
  p.add_argument("--limit", type=int, default=100)
  p.add_argument("--kind", nargs="+", default=["movie", "tv", "music", "audiobook", "spoken-word", "podcast"], choices=["movie", "tv", "music", "audiobook", "spoken-word", "podcast", "companion", "archive", "other", "sample", "video"])
  p.add_argument("--files", type=int, nargs="+")
  p.add_argument("--retry", action="store_true", help="Regenerate unreviewed proposals; never reopen a decision or import")
  p.add_argument("--refresh-metadata", action="store_true", help="Clear lookup cache before new proposals")
  p = sub.add_parser("review", help="Review prepared matches and import the selection")
  p.add_argument("--files", type=int, nargs="+")
  p.add_argument("--kind", nargs="+")
  p.add_argument("--limit", type=int, default=10)
  p = sub.add_parser("approve")
  p.add_argument("proposals", type=int, nargs="*")
  p.add_argument("--accepted", action="store_true", help="Preview all accepted, unbatched proposals")
  for name in ("apply", "verify"):
    p = sub.add_parser(name)
    p.add_argument("batch", type=int)
    if name == "verify":
      p.add_argument("--hash", action="store_true", help="Also read file contents and compare or establish SHA-256 baselines")
  p = sub.add_parser("export")
  p.add_argument("directory")
  p = sub.add_parser("show")
  p.add_argument("file", type=int)
  p = sub.add_parser("list")
  p.add_argument("--kind")
  p.add_argument("--contains", default="")
  p.add_argument("--state")
  p.add_argument("--limit", type=int, default=100)
  sub.add_parser("migrate-music-copies", help="Convert recorded music hardlinks before enabling tag writes")
  sub.add_parser("migrate-podcasts", help="Move the legacy spoken-word library to podcasts")
  p = sub.add_parser("repair-hardcore-history", help="Repair approved generic-album episodes as numbered series entries")
  p.add_argument("batch", type=int)
  p = sub.add_parser("reopen")
  p.add_argument("file", type=int)
  for name in ("run", "propose"):
    sub.choices[name].add_argument("--prep-workers", type=int, default=16, help="Parallel preparation workers (1–64; default 16); up to 4 simultaneous metadata queries")
  args = parser.parse_args()
  if args.command is None:
    args.command = "run"
  if args.command == "run" and args.kind is None:
    args.kind = ["movie", "tv", "music", "audiobook", "spoken-word", "podcast"]
  os.umask(0o077)
  try:
    if args.command in {"run", "review"} and args.limit < 1:
      raise ValueError("Review limit must be positive")
    config = json.loads(Path(args.config).read_text())
    if hasattr(args, "prep_workers"):
      if not 1 <= args.prep_workers <= 64:
        raise ValueError("Preparation workers must be between 1 and 64")
      config["prepWorkers"] = args.prep_workers
    if args.command == "configure":
      Apps(config).configure()
      return
    db = Path(config["database"])
    if args.command == "status":
      if not db.exists():
        raise ValueError("No audit database yet; run media-import inventory first")
      store = Store(db, config["source"], readonly=True)
      try:
        # One consistent WAL snapshot without blocking the import worker.
        store.db.execute("BEGIN")
        status(store)
      finally:
        store.db.close()
      return
    db.parent.mkdir(parents=True, exist_ok=True)
    if args.command == "hash":
      if args.limit is not None and args.limit < 1:
        raise ValueError("Hash limit must be positive")
      mount_check(config)
      precompute_hashes(config, args.limit, args.kind, args.files)
      return
    # Music review only reads torrent payloads; music workers only copy them.
    # They may coexist. Other commands retain exclusive coordination.
    music_review = args.command in {'run','review'} and args.kind == ['music'] and config.get('musicBackground')
    concurrent = music_review or args.command in {'work-queue','queue'}
    coordinator = (db.parent / 'coord.lock').open('a')
    fcntl.flock(coordinator, (fcntl.LOCK_SH if concurrent else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    lock_name = 'review.lock' if music_review else ('queue-status.lock' if args.command == 'queue' else 'audit.lock')
    with (db.parent / lock_name).open("a") as lock:
      try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
      except BlockingIOError:
        raise ValueError("Another media-import process is running") from None
      store = Store(db, config["source"])
      media_root = os.path.abspath(config["media"])
      previous_root = store.db.execute("SELECT value FROM meta WHERE key='media_root'").fetchone()
      if previous_root and previous_root[0] != media_root:
        raise ValueError("Library root changed; existing approvals cannot authorize a different destination root")
      store.db.execute("INSERT OR IGNORE INTO meta VALUES ('media_root', ?)", (media_root,))
      store.db.commit()
      if args.command in {"inventory", "propose", "apply", "verify", "approve", "run", "review", "repair-hardcore-history", "migrate-podcasts", "migrate-music-copies", "work-queue"}:
        mount_check(config)
      if args.command == 'queue':
        from .queue import show
        show(store)
      elif args.command == 'work-queue':
        from .queue import work
        work(store, config)
      elif args.command == "inventory":
        result = store.inventory()
        print(json.dumps(result, indent=2))
        if result["errors"]:
          raise ValueError("Incomplete scan: resolve errors before trusting inventory")
      elif args.command == "propose":
        if args.refresh_metadata:
          store.db.execute("DELETE FROM cache")
          store.db.commit()
        propose(store, config, args.limit, args.kind, args.files, args.retry)
      elif args.command in {"run", "review"}:
        try:
          interactive_import(store, config, args)
        finally:
          store.backup(config["localBackups"])
      elif args.command == "approve":
        if args.accepted and args.proposals:
          raise ValueError("Choose explicit proposals or --accepted")
        proposals = pending_proposals(store) if args.accepted else args.proposals
        batch = approve_batch(store, config, proposals)
        if batch:
          print(f"Approved batch {batch}; run media-import apply {batch}.")
      elif args.command == "apply":
        from .queue import finish
        try:
          apply_batch(store, config, args.batch)
        except Exception as exc:
          finish(store, args.batch, 'failed', str(exc))
          raise
        else:
          finish(store, args.batch, 'complete')
      elif args.command == "verify":
        store.backup(config["localBackups"])
        execute(store, config, args.batch, verify_only=True, verify_hashes=args.hash)
      elif args.command == "migrate-music-copies":
        from .music_copy import migrate
        migrate(store, config)
      elif args.command == "migrate-podcasts":
        from .migrate_podcasts import migrate
        migrate(store, config)
      elif args.command == "repair-hardcore-history":
        from .repair_hardcore_history import repair
        repair(store, config, args.batch)
      elif args.command == "status":
        status(store)
      elif args.command == "list":
        count = 0
        for row in store.report():
          if (args.kind and row["kind"] != args.kind) or (args.state and row["state"] != args.state) or args.contains.casefold() not in row["source"].casefold():
            continue
          print(f"#{row['file_id']} {row['kind']} {row['state']} {row['source']!r}")
          if row["reason"]:
            print("  ", row["reason"])
          count += 1
          if count >= args.limit:
            print("Display limit reached; use a narrower filter or --limit.")
            break
      elif args.command == "backup":
        mount_check(config)
        local = store.backup(config["localBackups"], force=True)
        target = Path(config["nasBackups"])
        target.mkdir(parents=True, exist_ok=True)
        temporary = target / ('.' + local.name + '.partial')
        for stale in target.glob('.audit-*.sqlite.partial'):
          if stale.is_file() and not stale.is_symlink():
            stale.unlink()
        print(f'Copying audit backup to NAS: {target / local.name}…', flush=True)
        try:
          shutil.copy2(local, temporary)
          with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
          temporary.replace(target / local.name)
          prune_audit_snapshots(target, 2)
        finally:
          temporary.unlink(missing_ok=True)
        print(f"NAS audit backup complete: {target / local.name}", flush=True)
      elif args.command == "export":
        store.export(args.directory)
      elif args.command == "show":
        for table, query in {
          "file": "SELECT * FROM files WHERE id=?",
          "revisions": "SELECT * FROM revisions WHERE file_id=?",
          "proposals": "SELECT p.* FROM proposals p JOIN revisions r ON r.id=p.revision_id WHERE r.file_id=?",
          "decisions": "SELECT d.* FROM decisions d JOIN revisions r ON r.id=d.revision_id WHERE r.file_id=?",
          "operations": "SELECT o.* FROM operations o JOIN proposals p ON p.id=o.proposal_id JOIN revisions r ON r.id=p.revision_id WHERE r.file_id=?",
        }.items():
          print(table, json.dumps([dict(r) for r in store.db.execute(query, (args.file,))], indent=2))
      elif args.command == "reopen":
        row = store.db.execute("SELECT current_revision FROM files WHERE id=?", (args.file,)).fetchone()
        if not row:
          raise ValueError("Unknown file")
        if store.db.execute("SELECT 1 FROM operations o JOIN proposals p ON p.id=o.proposal_id JOIN revisions r ON r.id=p.revision_id WHERE r.file_id=?", (args.file,)).fetchone():
          raise ValueError("Import operation exists: investigate/reconcile it instead of reopening")
        previous = store.db.execute("SELECT mapping FROM proposals WHERE revision_id=? ORDER BY id DESC LIMIT 1", (row[0],)).fetchone()
        # Keep all decisions. A new proposal revision is reviewed explicitly.
        mapping = edit_mapping(json.loads(previous[0]) if previous else {})
        new_id = store.propose(row[0], mapping)
        if key_choice("Keep this revised mapping? [y/N]: ", ["y", "n"], "n") == "y":
          validate_mapping(mapping, config)
          store.decide(row[0], "accept", "Explicitly reopened", new_id)
        store.backup(config["localBackups"])
  except (KeyboardInterrupt, EOFError):
    print("\nStopped. Saved decisions and completed hashes are retained.", file=sys.stderr)
    sys.exit(130)
  except (ValueError, OSError, subprocess.SubprocessError, KeyError) as exc:
    print(f"Stopped: {exc}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
