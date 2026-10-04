"""Crash-resumable independent music copies; original torrent bytes never change."""
import hashlib
import json
import os
from pathlib import Path

from .store import checksum, contained, packed, signature


def is_copy(mapping):
  return mapping['kind'] == 'music'


def state(store, operation):
  return store.db.execute('SELECT * FROM music_copies WHERE operation_id=?', (operation,)).fetchone()


def independent(source, destination):
  signature(destination)  # Reject symlinks and non-regular files.
  if os.path.samefile(source, destination) or destination.stat().st_nlink != 1:
    raise ValueError('Music destination is not an independent copy; refusing tag writes')


def owned(store, operation, source, destination):
  row = state(store, operation)
  if not row or row['phase'] != 'published':
    raise ValueError('Unrecorded music destination; refusing to overwrite it')
  independent(source, destination)
  observed = signature(destination)
  expected = json.loads(row['destination_signature'])
  if observed[3:] != expected[3:]:
    raise ValueError('Music destination was replaced outside the recorded import')


def copy_file(store, operation, source, destination, convert=False):
  """Publish only a complete, verified copy. Recovery uses saved temp inode/hash."""
  row = state(store, operation)
  if row and row['phase'] == 'published':
    owned(store, operation, source, destination)
    return
  old_umask = os.umask(0o007)
  try:
    destination.parent.mkdir(parents=True, exist_ok=True)
  finally:
    os.umask(old_umask)
  temp = destination.parent / f'.media-import-{operation}.copy-part'
  observed = signature(source)
  if not row:
    if destination.exists() and not (convert and os.path.samefile(source, destination)):
      raise ValueError('Music copy destination collision')
    if temp.exists() or temp.is_symlink():
      raise ValueError('Unrecorded copy staging file; inspect before resuming')
    store.db.execute('INSERT INTO music_copies(operation_id,phase,temp_path,source_signature,converting) VALUES (?,?,?,?,?)',
      (operation, 'copying', str(temp), packed(observed), int(convert)))
    store.db.commit()
    row = state(store, operation)
  if row['temp_path'] != str(temp):
    raise ValueError('Copy staging path differs from saved intent')
  expected_source = json.loads(row['source_signature'])
  # Detaching the old library hardlink changes source ctime, never its content.
  detached = row['converting'] and row['phase'] == 'ready' and destination.exists() and not os.path.samefile(source, destination)
  if observed != expected_source:
    if not (detached and observed[:2] == expected_source[:2] and observed[3:] == expected_source[3:] and checksum(source) == row['sha256']):
      raise ValueError('Source changed during music copy')
  if row['phase'] == 'copying':
    if destination.exists() and not (row['converting'] and os.path.samefile(source, destination)):
      raise ValueError('Destination appeared before copy publication')
    if temp.exists() or temp.is_symlink():
      signature(temp)
      if temp.stat().st_nlink != 1:
        raise ValueError('Copy staging file has unexpected hardlinks')
      temp.unlink()  # Only this operation-owned incomplete staging file.
    h = hashlib.sha256()
    with source.open('rb') as src, temp.open('xb') as dst:
      os.chmod(temp, 0o660)
      for block in iter(lambda: src.read(8 * 1024 * 1024), b''):
        h.update(block)
        dst.write(block)
      dst.flush()
      os.fsync(dst.fileno())
    if signature(source) != observed or checksum(temp) != h.hexdigest():
      raise ValueError('Source changed or copied bytes failed verification')
    store.db.execute("UPDATE music_copies SET phase='ready',sha256=?,destination_signature=? WHERE operation_id=?",
      (h.hexdigest(), packed(signature(temp)), operation))
    store.db.commit()
    row = state(store, operation)
  expected = json.loads(row['destination_signature'])
  if destination.exists() and not os.path.samefile(source, destination):
    if signature(destination)[3:] != expected[3:] or checksum(destination) != row['sha256']:
      raise ValueError('Destination collision during copy recovery')
  else:
    if not temp.exists() or signature(temp)[3:] != expected[3:] or checksum(temp) != row['sha256']:
      raise ValueError('Completed staging copy is missing or changed')
    if row['converting']:
      if not destination.exists() or not os.path.samefile(source, destination):
        raise ValueError('Legacy hardlink changed before conversion')
      os.replace(temp, destination)
    else:
      os.link(temp, destination)  # Atomic no-clobber publication of the COPY inode.
  if temp.exists():
    if not os.path.samefile(temp, destination):
      raise ValueError('Staging file no longer matches published copy')
    temp.unlink()
  independent(source, destination)
  directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
  try:
    os.fsync(directory)
  finally:
    os.close(directory)
  # Persist publication and the new source ctime together before any app call.
  with store.db:
    store.db.execute("UPDATE music_copies SET phase='published',destination_signature=? WHERE operation_id=?", (packed(signature(destination)), operation))
    store.db.execute('UPDATE operations SET verified_signature=? WHERE id=?', (packed(signature(source)), operation))
    store.event('music-copy-published', {'operation':operation, 'source':str(source), 'destination':str(destination), 'sha256':row['sha256'], 'convertedHardlink':bool(row['converting'])})


def migrate(store, config):
  """Run before enabling writable music/tagging; accepts only ledger-owned links."""
  from .cli import preflight_item
  import subprocess
  result = subprocess.run(['systemctl', 'is-active', 'lidarr.service'], capture_output=True, text=True)
  if result.stdout.strip() not in {'inactive', 'failed'}:
    raise ValueError('Stop Lidarr before converting legacy hardlinks')
  store.backup(config['localBackups'])
  for op in store.db.execute("SELECT * FROM operations WHERE status != 'superseded'").fetchall():
    batch = store.db.execute('SELECT manifest,digest FROM batches WHERE id=?', (op['batch_id'],)).fetchone()
    from .store import digest
    manifest = json.loads(batch['manifest'])
    if digest(manifest) != batch['digest']:
      raise ValueError('Manifest digest mismatch')
    item = next(x for x in manifest if x['proposal'] == op['proposal_id'])
    if not is_copy(item['mapping']):
      continue
    source = contained(store.root, item['source'])
    destination = contained(config['media'], item['mapping']['destination'])
    saved = state(store, op['id'])
    if saved and saved['phase'] != 'published':
      copy_file(store, op['id'], source, destination, convert=True)
    elif destination.exists():
      if saved:
        owned(store, op['id'], source, destination)
      else:
        preflight_item(store, config, item, op, allow_music_link=True)
        copy_file(store, op['id'], source, destination, convert=True)
      print(f'Independent music copy: {destination}', flush=True)
  # Reject every remaining hardlink/symlink in the writable library, including
  # files not managed by the ledger, before declaring it safe to enable tagging.
  assert_library_independent(Path(config['media']) / 'music')
  store.event('music-copy-migration-complete', {'root':str(Path(config['media']) / 'music')})
  store.db.commit()
  store.backup(config['localBackups'])


def assert_library_independent(root):
  if not root.is_dir() or root.is_symlink():
    raise ValueError('Music library root is missing or a symlink')
  def fail(error):
    raise error
  for directory, dirs, files in os.walk(root, onerror=fail):
    for name in dirs + files:
      path = Path(directory) / name
      if path.is_symlink():
        raise ValueError(f'Symlink in writable music library: {path}')
      if path.is_file() and path.stat().st_nlink != 1:
        raise ValueError(f'Hardlink in writable music library: {path}')
