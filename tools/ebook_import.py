"""qBittorrent completion queue, filesystem backfill, and ebook inbox handoff."""
import argparse
from collections import defaultdict
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request


FORMATS = {'.epub': 0, '.azw3': 1, '.mobi': 2, '.pdf': 3}
LEGACY = {'.azw', '.lit', '.html', '.htm', '.rtf', '.txt', '.doc', '.fb2', '.djvu'}
MAX_BYTES = 4 * 1024**3
MAX_FILE = 1024**3
MAX_FILES = 5000


def archive_part(path):
  return bool(re.search(r'\.(zip|rar|7z|r\d{2}|z\d{2}|7z\.\d{3}|zip\.\d{3})$', str(path), re.I))


def archive_start(path):
  name = path.name.lower()
  match = re.search(r'\.part(\d+)\.rar$', name)
  if match:
    return int(match[1]) == 1
  return name.endswith(('.zip', '.rar', '.7z', '.7z.001', '.zip.001'))


def safe_relative(name):
  path = PurePosixPath(name.replace('\\', '/'))
  if path.is_absolute() or '..' in path.parts or not path.parts or ':' in path.parts[0]:
    raise ValueError('Unsafe archive or torrent member path')
  return Path(*path.parts)


def checked_source(root, name):
  path = root / safe_relative(name)
  if any(p.is_symlink() for p in (path, *path.parents)):
    raise ValueError('Symlink in source path')
  if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
    raise ValueError('Source is missing or outside its torrent directory')
  return path


def normalized_stem(path):
  stem = path.stem.lower().removesuffix('.kepub')
  stem = re.sub(r'\((epub|azw3|mobi|pdf)\)$', '', stem)
  return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', stem)))


def choose(paths):
  groups = defaultdict(list)
  review = []
  skipped = 0
  for path in paths:
    if path.suffix.lower() in FORMATS:
      groups[(path.parent, normalized_stem(path))].append(path)
    elif path.suffix.lower() in LEGACY and not path.name.lower().startswith(('torrent', 'readme')):
      review.append({'reason': 'Legacy format requires review', 'files': [str(path)]})
    elif not archive_part(path):
      skipped += 1
  # Fuzzy similarity only flags uncertainty; it never merges different books.
  uncertain = set()
  keys = list(groups)
  for i, left in enumerate(keys):
    for right in keys[i + 1:]:
      if left[0] != right[0]:
        continue
      a, b = set(left[1].split()), set(right[1].split())
      left_formats = {p.suffix.lower() for p in groups[left]}
      right_formats = {p.suffix.lower() for p in groups[right]}
      if (a and b and left_formats != right_formats
          and len(a & b) / min(len(a), len(b)) >= 0.6):
        uncertain.update((left, right))
  selected = []
  alternatives = 0
  for key, group in groups.items():
    ranked = sorted(group, key=lambda p: (FORMATS[p.suffix.lower()], str(p)))
    if key in uncertain or (len(ranked) > 1 and ranked[0].suffix.lower() == ranked[1].suffix.lower()):
      review.append({'reason': 'Ambiguous editions or filenames', 'files': [str(p) for p in ranked]})
    else:
      selected.append(ranked[0])
      alternatives += len(ranked) - 1
  return selected, review, alternatives, skipped


def unpack(root, sevenzip='7zz'):
  """Extract members as streams, never allowing an archive to choose output paths."""
  processed = set()
  count = 0
  total = 0
  for depth in range(4):
    archives = sorted(p for p in root.rglob('*') if p.is_file() and archive_start(p) and p not in processed)
    if not archives:
      break
    for archive in archives:
      listing = subprocess.run([sevenzip, 'l', '-slt', '-ba', '-p', '--', str(archive)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
      if listing.returncode:
        raise ValueError(f'Cannot list archive (missing parts, password, or corruption): {archive.name}')
      for block in listing.stdout.split('\n\n'):
        fields = dict(line.split(' = ', 1) for line in block.splitlines() if ' = ' in line)
        if 'Path' not in fields:
          continue
        relative = safe_relative(fields['Path'])
        if fields.get('Symbolic Link') or fields.get('Hard Link'):
          raise ValueError('Archive contains a link')
        if fields.get('Folder') == '+' or fields.get('Attributes', '').startswith('D'):
          continue
        if relative.suffix.lower() not in set(FORMATS) | LEGACY and not archive_part(relative):
          continue
        size = int(fields.get('Size', '-1'))
        count += 1
        total += max(size, 0)
        if size < 0 or size > MAX_FILE or total > MAX_BYTES or count > MAX_FILES:
          raise ValueError('Archive exceeds extraction limits')
        target = archive.parent / relative
        if not target.resolve().is_relative_to(root.resolve()):
          raise ValueError('Archive output escapes staging')
        target.parent.mkdir(parents=True, exist_ok=True)
        def limit_output():
          resource.setrlimit(resource.RLIMIT_FSIZE, (size + 1, size + 1))
        # Packs can repeat an identical file across several archives. Compare
        # before publishing; different contents at the same path need review.
        fd, temporary_name = tempfile.mkstemp(dir=target.parent, prefix='.extract-')
        temporary = Path(temporary_name)
        try:
          with os.fdopen(fd, 'wb') as output:
            result = subprocess.run([sevenzip, 'x', '-so', '-spd', '-y', '-p', '--', str(archive), fields['Path']],
              stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL, timeout=120, preexec_fn=limit_output)
          if result.returncode or temporary.stat().st_size != size:
            raise ValueError(f'Archive extraction failed: {archive.name}')
          if target.exists():
            with target.open('rb') as existing, temporary.open('rb') as candidate:
              if hashlib.file_digest(existing, 'sha256').digest() != hashlib.file_digest(candidate, 'sha256').digest():
                raise ValueError(f'Archive output path collision: {target.relative_to(root)}')
          else:
            temporary.replace(target)
        finally:
          temporary.unlink(missing_ok=True)
      processed.add(archive)
  if any(p.is_file() and archive_start(p) and p not in processed for p in root.rglob('*')):
    raise ValueError('Archive nesting exceeds four levels')
  for part in root.rglob('*'):
    if not part.is_file() or not archive_part(part) or archive_start(part):
      continue
    name = part.name.lower()
    candidates = {p.name.lower() for p in processed if p.parent == part.parent}
    first = re.sub(r'\.(r\d{2})$', '.rar', name)
    first = re.sub(r'\.(z\d{2})$', '.zip', first)
    first = re.sub(r'\.(7z|zip)\.\d{3}$', r'.\1.001', first)
    first = re.sub(r'\.part(\d+)\.rar$', lambda m: '.part' + '1'.zfill(len(m[1])) + '.rar', first)
    if first not in candidates:
      raise ValueError(f'Archive part has no processed first volume: {part.name}')


def api(settings, endpoint, **query):
  url = settings['url'] + '/' + endpoint
  if query:
    url += '?' + urllib.parse.urlencode(query)
  with urllib.request.urlopen(url, timeout=30) as response:
    return json.load(response)


def torrent_sources(settings, torrent_id):
  rows = api(settings, 'torrents/info', hashes=torrent_id)
  if len(rows) != 1:
    raise ValueError('Torrent is no longer present')
  torrent = rows[0]
  if torrent['category'] != 'books':
    return None
  if torrent['amount_left'] != 0:
    raise ValueError('Torrent is not complete yet')
  root = Path(torrent['save_path'])
  if not root.resolve().is_relative_to(Path(settings['source']).resolve()):
    raise ValueError('Torrent is outside the configured source tree')
  sources = []
  for entry in api(settings, 'torrents/files', hash=torrent_id):
    if entry['priority'] == 0:
      continue
    if entry['progress'] != 1:
      raise ValueError('Selected torrent file is incomplete')
    path = checked_source(root, entry['name'])
    if path.stat().st_size != entry['size']:
      raise ValueError('Torrent file size does not match its file list')
    sources.append((path, safe_relative(entry['name'])))
  return sources


def connect(state):
  db = sqlite3.connect(state / 'state.sqlite', timeout=30)
  db.execute('PRAGMA journal_mode=WAL')
  db.executescript('''
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
      detail TEXT NOT NULL DEFAULT '', updated REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS delivered (
      hash TEXT PRIMARY KEY, filename TEXT NOT NULL, status TEXT NOT NULL
    );
  ''')
  return db


def recover(db, settings):
  incoming, outbox = Path(settings['incoming']), Path(settings['outbox'])
  for digest, filename in db.execute("SELECT hash, filename FROM delivered WHERE status='prepared'").fetchall():
    staged, target = outbox / digest, incoming / filename
    if staged.exists():
      if target.exists():
        with target.open('rb') as source:
          if hashlib.file_digest(source, 'sha256').hexdigest() != digest:
            raise ValueError('Inbox filename collision')
        staged.unlink()
      else:
        staged.replace(target)
    # No staged file means it was published, possibly already consumed by CWA.
    db.execute("UPDATE delivered SET status='done' WHERE hash=?", (digest,))
    db.commit()


def deliver(db, settings, source):
  before = source.stat()
  if before.st_size > MAX_FILE:
    raise ValueError('Ebook exceeds 1 GiB limit')
  fd, name = tempfile.mkstemp(dir=settings['outbox'], prefix='copy-')
  staged = Path(name)
  try:
    digest = hashlib.sha256()
    with os.fdopen(fd, 'wb') as output, source.open('rb') as input_file:
      for chunk in iter(lambda: input_file.read(1024 * 1024), b''):
        digest.update(chunk)
        output.write(chunk)
      output.flush()
      os.fsync(output.fileno())
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
      raise ValueError('Source changed while copying')
    checksum = digest.hexdigest()
    if db.execute('SELECT 1 FROM delivered WHERE hash=?', (checksum,)).fetchone():
      return False
    stem = re.sub(r'[^\w .()-]', '_', source.stem)[:100]
    filename = f'{stem}--{checksum[:16]}{source.suffix.lower()}'
    staged.chmod(0o660)
    staged.replace(Path(settings['outbox']) / checksum)
    db.execute('INSERT INTO delivered VALUES (?, ?, ?)', (checksum, filename, 'prepared'))
    db.commit()
    recover(db, settings)
    return True
  finally:
    staged.unlink(missing_ok=True)


def process(db, settings, torrent_id):
  sources = torrent_sources(settings, torrent_id)
  if sources is None:
    return 'ignored', {'reason': 'Category is not books'}
  return process_sources(db, settings, sources)


def process_sources(db, settings, sources, dry_run=False):
  if len(sources) > MAX_FILES:
    raise ValueError('Torrent exceeds file-count limit')
  with tempfile.TemporaryDirectory(dir=settings['work'], prefix='extract-') as directory:
    root = Path(directory)
    input_bytes = 0
    ignored = 0
    for source, relative in sources:
      if archive_part(source) or source.suffix.lower() in set(FORMATS) | LEGACY:
        before = source.stat()
        input_bytes += before.st_size
        if input_bytes > MAX_BYTES:
          raise ValueError('Ebook input exceeds 4 GiB limit')
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
          raise ValueError('Torrent source changed while staging')
      else:
        ignored += 1
    unpack(root, settings['sevenzip'])
    extracted = [p for p in root.rglob('*') if p.is_file() and not archive_part(p)]
    selected, review, alternatives, skipped = choose(extracted)
    candidates = []
    copied = 0
    already = 0
    seen = set()
    for path in selected:
      with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
      duplicate = digest in seen or db.execute('SELECT 1 FROM delivered WHERE hash=?', (digest,)).fetchone() is not None
      seen.add(digest)
      candidates.append({'file': str(path.relative_to(root)), 'sha256': digest,
        'action': 'alreadyDelivered' if duplicate else 'copy'})
      if duplicate:
        already += 1
      elif not dry_run:
        copied += deliver(db, settings, path)
    # Persist paths relative to the extraction directory, not temporary names.
    for item in review:
      item['files'] = [p.replace(str(root) + '/', 'staged:') for p in item['files']]
    return ('review' if review else 'done'), {
      'copied': copied, 'alreadyDelivered': already, 'candidates': candidates,
      'alternativesSkipped': alternatives, 'otherFilesSkipped': skipped + ignored, 'review': review,
    }


def backfill(db, settings, directory, apply=False, limit=None, exclude=()):
  directory = directory.absolute()
  if directory.is_symlink() or not directory.is_dir() or not directory.resolve().is_relative_to(Path(settings['source']).resolve()):
    raise ValueError('Backfill directory must be inside the configured torrent source')
  groups = []
  loose = []
  for path in sorted(directory.iterdir()):
    if path.is_dir() and not path.is_symlink():
      groups.append((path.name, sorted(p for p in path.rglob('*') if p.is_file() or p.is_symlink())))
    else:
      loose.append(path)
  if loose:
    groups.insert(0, ('.', loose))
  report = {'directory': str(directory), 'apply': apply, 'groups': []}
  for label, paths in groups[:limit]:
    try:
      if label in exclude:
        raise ValueError('Collection excluded for manual review')
      # Resolve only candidate ebook/archive files; comic and audio payloads
      # cannot enter the ebook staging area. Validate all selected paths.
      sources = [(checked_source(directory, str(p.relative_to(directory))), p.relative_to(directory))
        for p in paths if p.suffix.lower() in set(FORMATS) | LEGACY or archive_part(p)]
      status, detail = process_sources(db, settings, sources, dry_run=not apply)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
      status, detail = 'review', {'error': str(error)}
    result = {'folder': label, 'status': status, **detail}
    report['groups'].append(result)
    # Keep a single current report, separate from the durable delivery ledger.
    target = Path(settings['state']) / ('backfill-report.json' if apply else 'backfill-preview.json')
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n')
    temporary.replace(target)
    print(json.dumps(result), flush=True)
  return report


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--config', default='/etc/ebook-import.json')
  sub = parser.add_subparsers(dest='command', required=True)
  enqueue = sub.add_parser('enqueue')
  enqueue.add_argument('torrent_id')
  enqueue.add_argument('category')
  retry = sub.add_parser('retry')
  retry.add_argument('torrent_id')
  sub.add_parser('work')
  sub.add_parser('status')
  preview = sub.add_parser('preview')
  preview.add_argument('directory', type=Path)
  fill = sub.add_parser('backfill', help='Preview filesystem imports; --apply copies selected books')
  fill.add_argument('directory', type=Path)
  fill.add_argument('--apply', action='store_true')
  fill.add_argument('--limit', type=int, help='Process at most this many top-level groups')
  fill.add_argument('--exclude', action='append', default=[], metavar='FOLDER',
    help='Hold a top-level folder for manual review (repeatable)')
  args = parser.parse_args()
  if args.command == 'backfill' and args.limit is not None and args.limit < 1:
    parser.error('--limit must be positive')
  if args.command == 'preview':
    paths = [p for p in args.directory.rglob('*') if p.is_file() and not p.is_symlink()]
    selected, review, alternatives, skipped = choose(paths)
    print(json.dumps({'selected': [str(p) for p in selected], 'review': review,
      'alternativesSkipped': alternatives, 'otherFilesSkipped': skipped,
      'archivesNotExtracted': sum(archive_part(p) for p in paths)}, indent=2))
    return
  settings = json.loads(Path(args.config).read_text())
  state = Path(settings['state'])
  if args.command in ('enqueue', 'retry'):
    if not re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', args.torrent_id):
      raise ValueError('Invalid torrent ID')
    if args.command == 'enqueue' and args.category != 'books':
      return
  with contextlib.closing(connect(state)) as db:
    if args.command == 'enqueue':
      db.execute("INSERT OR IGNORE INTO jobs (id,status,updated) VALUES (?,'pending',?)", (args.torrent_id.lower(), time.time()))
      db.commit()
    elif args.command == 'retry':
      db.execute("UPDATE jobs SET status='pending',attempts=0,updated=? WHERE id=?", (time.time(), args.torrent_id.lower()))
      db.commit()
    elif args.command == 'status':
      for row in db.execute('SELECT id,status,attempts,detail FROM jobs ORDER BY updated DESC'):
        print(json.dumps(dict(zip(('torrent','status','attempts','detail'), row))))
    else:
      import fcntl
      with (state / 'worker.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # A killed worker can leave scratch files; no other worker holds this lock.
        for path in Path(settings['work']).glob('extract-*'):
          shutil.rmtree(path)
        for path in Path(settings['outbox']).iterdir():
          if path.name.startswith('copy-') or not db.execute('SELECT 1 FROM delivered WHERE hash=?', (path.name,)).fetchone():
            path.unlink()
        recover(db, settings)
        if args.command == 'backfill':
          backfill(db, settings, args.directory, apply=args.apply, limit=args.limit, exclude=args.exclude)
          return
        jobs = db.execute("SELECT id,attempts FROM jobs WHERE status='pending' ORDER BY updated LIMIT 10").fetchall()
        for torrent_id, attempts in jobs:
          try:
            status, detail = process(db, settings, torrent_id)
          except (OSError, ValueError, subprocess.SubprocessError) as error:
            status = 'review' if attempts >= 2 else 'pending'
            detail = {'error': str(error)}
          db.execute('UPDATE jobs SET status=?,attempts=?,detail=?,updated=? WHERE id=?',
            (status, attempts + 1, json.dumps(detail), time.time(), torrent_id))
          db.commit()
          print(json.dumps({'torrent': torrent_id, 'status': status, **detail}), flush=True)
        # Ignored events are disposable; successful hashes are durable dedup state.
        db.execute("DELETE FROM jobs WHERE status='ignored' AND updated < ?", (time.time() - 14 * 86400,))
        # Successful per-job reports expire; IDs and content hashes are dedup state.
        db.execute("UPDATE jobs SET detail='' WHERE status='done' AND updated < ?", (time.time() - 14 * 86400,))
        db.commit()


if __name__ == '__main__':
  main()
