"""Incremental migration CLI. All media writes require an approved manifest."""
import argparse
import collections
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from .apps import Apps
from .store import Store, checksum, contained, digest, packed, signature


def mount_check(config):
  source = Path(config["source"])
  if not source.is_dir():
    raise ValueError("Torrent source directory is unavailable")
  mount = config["mount"]
  result = subprocess.run(["findmnt", "-J", "-T", str(source), "-o", "SOURCE,FSTYPE,TARGET"], check=True, capture_output=True, text=True)
  mounts = json.loads(result.stdout)["filesystems"]
  if not any(m["source"] == mount["source"] and m["fstype"] in {"nfs", "nfs4"} and m["target"] == mount["target"] for m in mounts):
    raise ValueError("Expected NAS mount is absent; refusing to scan or write")


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
  if kind not in {"movie", "tv", "music", "audiobook", "spoken-word", "video"}:
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


def propose(store, config, limit, kinds=None, files=None, retry=False):
  apps = Apps(config)
  count = 0
  for row in store.candidates(config.get("stabilitySeconds", 600), retry=retry):
    if (kinds and row["kind"] not in kinds) or (files and row["id"] not in files):
      continue
    if count >= limit:
      break
    path = contained(store.root, row["path"])
    evidence = {"source": row["path"], "classification": row["kind"]}
    options, issue = [], ""
    try:
      if signature(path) != json.loads(row["signature"]):
        raise ValueError("Source changed; inventory again")
      probe = json.loads(row["probe"]) if row["probe"] else inspect_file(path, row["kind"])
      if signature(path) != json.loads(row["signature"]):
        raise ValueError("Source changed during inspection")
      store.db.execute("UPDATE revisions SET probe=? WHERE id=?", (packed(probe), row["revision_id"]))
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
        cached = store.db.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
        lookup = json.loads(cached[0]) if cached else apps.lookup(row["kind"], query)
        store.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, packed(lookup), time.time()))
        evidence["query"] = query
        evidence["candidates"] = lookup["results"]
        for candidate in lookup["results"][:10]:
          try:
            options.append(mapping_for(row["kind"], row["path"], candidate, evidence, lookup["version"]))
          except (KeyError, ValueError, TypeError) as exc:
            issue = str(exc)
        if len(options) != 1:
          issue = issue or f"{len(options)} candidate mappings; select an identity"
      elif row["kind"] in {"audiobook", "spoken-word"}:
        tags = guess(Path(row["path"]), probe)["tags"]
        title = tags.get("album", "")
        author = tags.get("albumartist", tags.get("artist", ""))
        if title and author:
          folder = ("spoken-word" if row["kind"] == "spoken-word" else "audiobooks") + f"/{clean(author)}/{clean(title)}"
          order = int(str(tags.get("track", tags.get("tracknumber", 1))).split("/")[0])
          options = [{"kind": row["kind"], "identity": {"title": title, "author": author}, "order": order, "destination": f"{folder}/{path.name}", "entityPath": folder, "evidence": evidence}]
        issue = "Confirm book/collection identity and multipart order from tags"
      else:
        issue = {"archive": "Hand audit archive; extraction is disabled", "partial": "Incomplete/temporary transfer; never import", "companion": "Assign to an approved parent release or explicitly retain at source", "sample": "Confirm sample exclusion", "other": "Classify non-media or deferred category", "video": "Video outside movie/TV categories; explicit classification needed"}.get(row["kind"], "Manual classification needed")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
      issue = str(exc)
    store.propose(row["revision_id"], {"kind": row["kind"], "options": options, "issue": issue, "evidence": evidence})
    count += 1
  print(f"Created {count} review records. Nothing imported.")


def validate_mapping(mapping, config):
  for key in ("kind", "identity", "destination", "entityPath"):
    if not mapping.get(key):
      raise ValueError(f"Missing mapping field: {key}")
  kind = mapping["kind"]
  root = {"movie": "movies", "tv": "tv", "music": "music", "audiobook": "audiobooks", "spoken-word": "spoken-word", "companion": None}.get(kind)
  if kind not in {"movie", "tv", "music", "audiobook", "spoken-word", "companion"}:
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
  if kind in {"audiobook", "spoken-word"} and (not isinstance(mapping.get("order"), int) or mapping["order"] < 1 or not mapping["identity"].get("author")):
    raise ValueError("Audiobooks require an author and explicit 1-based file order")
  return path


def edit_mapping(mapping):
  with tempfile.TemporaryDirectory(prefix="media-review-") as temp:
    path = Path(temp) / "mapping.json"
    path.write_text(json.dumps(mapping, indent=2) + "\n")
    subprocess.run(shlex.split(os.environ.get("EDITOR", "vi")) + [str(path)], check=True)
    return json.loads(path.read_text())


def review(store, config, ids=None):
  rows = store.db.execute("""SELECT p.*,f.path,f.kind,f.id AS file_id FROM proposals p
    JOIN revisions r ON r.id=p.revision_id JOIN files f ON f.current_revision=r.id
    WHERE f.present=1 AND p.id=(SELECT MAX(p2.id) FROM proposals p2 WHERE p2.revision_id=r.id)
    AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.revision_id=r.id)
    ORDER BY f.path""").fetchall()
  accepted = []
  handled = set()
  for row in rows:
    if row["revision_id"] in handled:
      continue
    if ids and row["file_id"] not in ids:
      continue
    proposal = json.loads(row["mapping"])
    print(f"\nFile #{row['file_id']} | {row['kind']} | {row['path']}")
    print(proposal.get("issue", "Verify proposed mapping"))
    options = proposal.get("options", [proposal] if proposal.get("destination") else [])
    for i, option in enumerate(options, 1):
      print(f"  {i}: {packed(option['identity'])}\n     -> {option['destination']}")
    answer = input("Number=select, v=evidence, e=edit mapping, x=exclude, d=defer, q=save/quit: ").strip()
    while answer == "v":
      print(json.dumps(proposal.get("evidence", proposal), indent=2))
      answer = input("Number/e/x/d/q: ").strip()
    if answer == "q":
      break
    if answer in {"x", "d"}:
      reason = input("Reason: ").strip()
      if reason:
        store.decide(row["revision_id"], "exclude" if answer == "x" else "defer", reason, row["id"])
      continue
    if answer == "e":
      mapping = edit_mapping(options[0] if options else {"kind": row["kind"], "identity": {}, "entityPath": "", "destination": "", "evidence": proposal.get("evidence", {})})
    elif answer.isdigit() and 1 <= int(answer) <= len(options):
      mapping = options[int(answer) - 1]
      if mapping.get("releaseChoices"):
        for i, release in enumerate(mapping["releaseChoices"], 1):
          print(i, packed(release))
        choice = input("MusicBrainz release number (blank=defer): ").strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(mapping["releaseChoices"]):
          continue
        mapping["identity"]["foreignReleaseId"] = mapping["releaseChoices"][int(choice) - 1]["foreignReleaseId"]
    else:
      continue
    validate_mapping(mapping, config)
    print(json.dumps({k: v for k, v in mapping.items() if k not in {"evidence", "releaseChoices"}}, indent=2))
    answer = input("accept=this file, group=season/album preview, alternate=retain outside app, Enter=skip: ").strip()
    if answer == "alternate":
      mapping["entityPath"] = "alternates/" + mapping["entityPath"]
      mapping["destination"] = "alternates/" + mapping["destination"]
      mapping["alternate"] = True
      validate_mapping(mapping, config)
      print("Alternate destination:", mapping["destination"])
      answer = input("Type accept to save this alternate mapping: ").strip()
    if answer == "group" and mapping["kind"] in {"tv", "music", "audiobook", "spoken-word"}:
      group = []
      for other in rows:
        if other["revision_id"] in handled or (ids and other["file_id"] not in ids):
          continue
        data = json.loads(other["mapping"])
        for option in data.get("options", [data] if data.get("destination") else []):
          if option.get("kind") != mapping["kind"] or option.get("entityPath") != mapping["entityPath"]:
            continue
          if mapping["kind"] == "tv" and option.get("season") != mapping["season"]:
            continue
          if mapping["kind"] == "music" and option["identity"].get("foreignAlbumId") != mapping["identity"]["foreignAlbumId"]:
            continue
          if mapping["kind"] == "music":
            option["identity"]["foreignReleaseId"] = mapping["identity"]["foreignReleaseId"]
          validate_mapping(option, config)
          group.append((other, option))
          break
      print("\nExact group mappings:")
      for other, option in group:
        assignment = {k: option[k] for k in ("season", "episodes", "disc", "track", "order") if k in option}
        print(f"#{other['file_id']} {other['path']}\n  {packed(assignment)} -> {option['destination']}")
      if input(f"Accept these {len(group)} mappings? Type accept-group: ").strip() == "accept-group":
        for other, option in group:
          new_id = store.propose(other["revision_id"], option)
          store.decide(other["revision_id"], "accept", "Accepted exact terminal group preview", new_id)
          accepted.append(new_id)
          handled.add(other["revision_id"])
      continue
    if answer != "accept":
      continue
    new_id = store.propose(row["revision_id"], mapping)
    store.decide(row["revision_id"], "accept", "Accepted in terminal review", new_id)
    accepted.append(new_id)
  print(f"Accepted proposals this session: {accepted}. Use approve to create an executable batch.")


def preflight_item(store, config, item, op):
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
  # when the recorded pre-hash, inode, and actual destination link all agree.
  recovering_link = op["status"] != "verified" and op["before_hash"] and destination.exists() and os.path.samefile(source, destination)
  if sig != expected and not (recovering_link and sig[:2] == expected[:2] and sig[3:] == expected[3:] and checksum(source) == op["before_hash"]):
    raise ValueError("Source changed since approval; do not import")
  if destination.exists() and not os.path.samefile(source, destination):
    raise ValueError(f"Destination collision: {destination}")
  return source, destination


def execute(store, config, batch_id, apps=None, verify_only=False):
  apps = Apps(config) if apps is None else apps
  batch = store.db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
  if not batch:
    raise ValueError("Unknown batch")
  manifest = json.loads(batch["manifest"])
  if digest(manifest) != batch["digest"]:
    raise ValueError("Manifest digest mismatch")
  media = Path(config["media"])
  # Preflight the complete batch before changing any library entry.
  for item in manifest:
    op = store.db.execute("SELECT * FROM operations WHERE proposal_id=?", (item["proposal"],)).fetchone()
    if op["status"] != "verified" or verify_only:
      preflight_item(store, config, item, op)
  for item in manifest:
    op = store.db.execute("SELECT * FROM operations WHERE proposal_id=?", (item["proposal"],)).fetchone()
    if op["status"] == "verified" and not verify_only:
      continue
    try:
      source, destination = preflight_item(store, config, item, op)
      before = op["before_hash"]
      if not before:
        if verify_only:
          raise ValueError("No pre-import hash; apply the approved batch first")
        print(f"Hashing {item['source']}", flush=True)
        before = checksum(source)
        duplicate = store.db.execute("SELECT id FROM operations WHERE before_hash=? AND id<>? LIMIT 1", (before, op["id"])).fetchone()
        if duplicate and not item["mapping"].get("alternate") and not item["mapping"].get("duplicateAcknowledged"):
          raise ValueError(f"Same content as operation {duplicate['id']}; review as duplicate")
        store.db.execute("UPDATE operations SET before_hash=?,status='hashed' WHERE id=?", (before, op["id"]))
        store.db.commit()
      elif checksum(source) != before:
        raise ValueError("Source hash changed since operation began")
      record = json.loads(op["app_record"]) if op["app_record"] else None
      if not verify_only:
        before_prepare = signature(source)
        if record is None:
          record = apps.prepare(item["mapping"], media)
          if any(path != str(destination) for path in record.get("existingPaths", [])):
            raise ValueError("App already has a file for this identity; replacement is prohibited")
          store.db.execute("UPDATE operations SET app_record=?,status='prepared' WHERE id=?", (packed(record), op["id"]))
          store.db.commit()
        if not destination.exists():
          if signature(source) != before_prepare:
            raise ValueError("Source changed during app preparation")
          old_umask = os.umask(0o007)
          try:
            destination.parent.mkdir(parents=True, exist_ok=True)
          finally:
            os.umask(old_umask)
          # No fallback copy, rename, unlink, chmod, or tag modification.
          os.link(source, destination, follow_symlinks=False)
        if not os.path.samefile(source, destination):
          raise ValueError("Destination is not a hardlink")
        store.db.execute("UPDATE operations SET status='linked',verified_signature=? WHERE id=?", (packed(signature(source)), op["id"]))
        store.db.commit()
        apps.scan(record)
      if record is None or not destination.exists() or not os.path.samefile(source, destination):
        raise ValueError("Missing app record or verified hardlink")
      record = apps.verify(record, item["mapping"], destination)
      if checksum(source) != before:
        raise ValueError("Source content changed during import; stop and investigate")
      if not os.path.samefile(source, destination):
        raise ValueError("App replaced the hardlink")
      store.db.execute("UPDATE operations SET status='verified',verified_signature=?,app_record=?,error=NULL WHERE id=?", (packed(signature(source)), packed(record), op["id"]))
      store.event("verified", {"operation": op["id"], "sha256": before, "destination": str(destination)})
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
  for (kind, state), number in sorted(counts.items()):
    print(f"{number:7d}  {kind:14s} {state}")
  last = store.db.execute("SELECT id,errors FROM scans ORDER BY id DESC LIMIT 1").fetchone()
  if last and json.loads(last["errors"]):
    print("LAST SCAN INCOMPLETE:", last["errors"])


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--config", default="/etc/media-import.json")
  sub = parser.add_subparsers(dest="command", required=True)
  for name in ("inventory", "status", "configure", "backup"):
    sub.add_parser(name)
  p = sub.add_parser("propose")
  p.add_argument("--limit", type=int, default=100)
  p.add_argument("--kind", nargs="+", default=["movie", "tv", "music", "audiobook", "spoken-word"], choices=["movie", "tv", "music", "audiobook", "spoken-word", "companion", "archive", "other", "sample", "video"])
  p.add_argument("--files", type=int, nargs="+")
  p.add_argument("--retry", action="store_true", help="Regenerate unreviewed proposals; never reopen a decision or import")
  p.add_argument("--refresh-metadata", action="store_true", help="Clear lookup cache before new proposals")
  p = sub.add_parser("review")
  p.add_argument("--files", type=int, nargs="+")
  p = sub.add_parser("approve")
  p.add_argument("proposals", type=int, nargs="*")
  p.add_argument("--accepted", action="store_true", help="Preview all accepted, unbatched proposals")
  for name in ("apply", "verify"):
    p = sub.add_parser(name)
    p.add_argument("batch", type=int)
  p = sub.add_parser("export")
  p.add_argument("directory")
  p = sub.add_parser("show")
  p.add_argument("file", type=int)
  p = sub.add_parser("list")
  p.add_argument("--kind")
  p.add_argument("--contains", default="")
  p.add_argument("--state")
  p.add_argument("--limit", type=int, default=100)
  p = sub.add_parser("reopen")
  p.add_argument("file", type=int)
  args = parser.parse_args()
  os.umask(0o077)
  try:
    config = json.loads(Path(args.config).read_text())
    if args.command == "configure":
      Apps(config).configure()
      return
    db = Path(config["database"])
    db.parent.mkdir(parents=True, exist_ok=True)
    with (db.parent / "audit.lock").open("a") as lock:
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
      if args.command in {"inventory", "propose", "apply", "verify", "approve"}:
        mount_check(config)
      if args.command == "inventory":
        result = store.inventory()
        print(json.dumps(result, indent=2))
        if result["errors"]:
          raise ValueError("Incomplete scan: resolve errors before trusting inventory")
      elif args.command == "propose":
        if args.refresh_metadata:
          store.db.execute("DELETE FROM cache")
          store.db.commit()
        propose(store, config, args.limit, args.kind, args.files, args.retry)
      elif args.command == "review":
        try:
          review(store, config, args.files)
        finally:
          store.backup(config["localBackups"])
      elif args.command == "approve":
        if args.accepted:
          if args.proposals:
            raise ValueError("Choose explicit proposal IDs or --accepted, not both")
          args.proposals = [r[0] for r in store.db.execute("""SELECT p.id FROM proposals p
            JOIN decisions d ON d.proposal_id=p.id JOIN revisions r ON r.id=p.revision_id
            JOIN files f ON f.current_revision=r.id
            WHERE d.action='accept' AND f.present=1
            AND d.id=(SELECT MAX(d2.id) FROM decisions d2 WHERE d2.revision_id=r.id)
            AND NOT EXISTS (SELECT 1 FROM operations o WHERE o.proposal_id=p.id)
            ORDER BY p.id""")]
        if not args.proposals:
          raise ValueError("No accepted proposals to approve")
        for proposal_id in args.proposals:
          row = store.db.execute("SELECT mapping FROM proposals WHERE id=?", (proposal_id,)).fetchone()
          if not row:
            raise ValueError(f"Unknown proposal {proposal_id}")
          mapping = json.loads(row[0])
          validate_mapping(mapping, config)
          print(proposal_id, packed({k: v for k, v in mapping.items() if k != "evidence"}))
        if input("Confirm all transfers finished and approve EXACTLY these proposals: type approve: ") != "approve":
          raise ValueError("Batch not approved")
        batch = store.batch(args.proposals)
        store.backup(config["localBackups"])
        print(f"Approved batch {batch}; run media-import apply {batch} separately.")
      elif args.command in {"apply", "verify"}:
        if args.command == "apply" and not store.db.execute("SELECT 1 FROM operations WHERE batch_id=? AND status<>'verified'", (args.batch,)).fetchone():
          if not store.db.execute("SELECT 1 FROM batches WHERE id=?", (args.batch,)).fetchone():
            raise ValueError("Unknown batch")
          print("Batch already verified; no operations performed.")
          return
        store.backup(config["localBackups"])
        if args.command == "apply":
          # Backup app state using each application's own supported command.
          manifest = store.db.execute("SELECT manifest FROM batches WHERE id=?", (args.batch,)).fetchone()
          if not manifest:
            raise ValueError("Unknown batch")
          names = { {"movie": "radarr", "tv": "sonarr", "music": "lidarr"}.get(x["mapping"]["kind"]) for x in json.loads(manifest[0]) }
          for name in sorted(n for n in names if n):
            Apps(config).api(name).command("Backup")
          if any(x["mapping"]["kind"] in {"audiobook", "spoken-word"} for x in json.loads(manifest[0])):
            Apps(config).api("audiobookshelf").call("backups", "POST", {})
        execute(store, config, args.batch, verify_only=args.command == "verify")
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
        local = store.backup(config["localBackups"])
        target = Path(config["nasBackups"])
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local, target / local.name)
        print(target / local.name)
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
        if input("Type accept to accept this revised mapping (otherwise remains deferred): ") == "accept":
          validate_mapping(mapping, config)
          store.decide(row[0], "accept", "Explicitly reopened", new_id)
        store.backup(config["localBackups"])
  except (ValueError, OSError, subprocess.SubprocessError, KeyError) as exc:
    print(f"Stopped: {exc}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
