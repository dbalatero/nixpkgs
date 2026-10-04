"""Apply an explicitly reviewed subtitle plan using the existing audited importer.

Usage: python -m media_import.companion_backfill PLAN.json [--apply]
The plan must name each subtitle and its verified movie/TV parent operation.
"""
import argparse
import fcntl
import json
import os
import time
from pathlib import Path

from .store import Store, contained, digest, packed, signature


def validate(store, config, plan):
  from .cli import validate_mapping
  if plan['source'] != config['source'] or plan['media'] != config['media']:
    raise ValueError('Plan roots do not match configured roots')
  destinations = set()
  sources = {item['source'] for item in plan['items']}
  if len(sources) != len(plan['items']) or not sources:
    raise ValueError('Empty plan or duplicate source')
  for item in plan['items']:
    row = store.db.execute('SELECT * FROM files WHERE id=?', (item['fileId'],)).fetchone()
    if not row or not row['present'] or row['path'] != item['source'] or row['current_revision'] != item['revision']:
      raise ValueError('Subtitle inventory changed since planning')
    if store.db.execute('''SELECT 1 FROM operations o JOIN proposals p ON p.id=o.proposal_id
      JOIN revisions r ON r.id=p.revision_id WHERE r.file_id=?''', (item['fileId'],)).fetchone():
      raise ValueError('Subtitle already belongs to an import operation')
    source = contained(store.root, item['source'])
    if source.suffix.lower() not in {'.sub', '.idx', '.srt', '.ass', '.ssa', '.vtt', '.smi', '.sup'}:
      raise ValueError('Not a supported subtitle extension')
    if source.suffix.lower() in {'.sub', '.idx'}:
      counterpart = str(Path(item['source']).with_suffix('.idx' if source.suffix.lower() == '.sub' else '.sub'))
      if counterpart not in sources:
        raise ValueError('VobSub pair must be imported together')
    if signature(source) != item['signature']:
      raise ValueError(f'Subtitle changed: {source}')
    revision = store.db.execute('SELECT signature FROM revisions WHERE id=?', (item['revision'],)).fetchone()
    inventoried = json.loads(revision[0])
    if inventoried != item.get('inventorySignature', item['signature']):
      raise ValueError('Planned source does not match inventoried revision')
    # NFS device numbers can change after a remount. Size, mtime, ctime and
    # inode must still match; mount_check verifies the configured server/export.
    if inventoried[:3] + inventoried[4:] != item['signature'][:3] + item['signature'][4:]:
      raise ValueError('Source changed beyond its NFS device number')
    parent = store.db.execute('''SELECT o.status,p.mapping,p.revision_id,f.current_revision,f.path,f.present
      FROM operations o JOIN proposals p ON p.id=o.proposal_id
      JOIN revisions r ON r.id=p.revision_id JOIN files f ON f.id=r.file_id
      WHERE o.id=?''', (item['parentOperation'],)).fetchone()
    if not parent or parent['status'] != 'verified' or not parent['present'] or parent['revision_id'] != parent['current_revision']:
      raise ValueError('Parent video is no longer verified')
    mapping = store.relocate_mapping(json.loads(parent['mapping']))
    if mapping['kind'] not in {'movie', 'tv'} or mapping.get('alternate'):
      raise ValueError('Parent is not a managed movie/episode')
    if parent['path'] != item['parentSource'] or mapping['destination'] != item['parentDestination']:
      raise ValueError('Parent mapping changed')
    if Path(parent['path']).parts[:2] != Path(item['source']).parts[:2]:
      raise ValueError('Subtitle and parent belong to different source releases')
    video = contained(config['media'], mapping['destination'])
    if not os.path.samefile(contained(store.root, parent['path']), video):
      raise ValueError('Parent video hardlink is missing or replaced')
    companion = item['mapping']
    if companion['kind'] != 'companion' or companion.get('alternate') or companion['identity'] != mapping['identity'] or companion['entityPath'] != mapping['entityPath']:
      raise ValueError('Companion identity differs from its parent')
    destination = validate_mapping(companion, config)
    if destination.parent != video.parent or not destination.name.startswith(video.stem + '.') or destination.suffix.lower() != source.suffix.lower():
      raise ValueError('Subtitle must use the parent video name and directory')
    key = str(destination).casefold()
    if key in destinations:
      raise ValueError('Subtitle destination collision within plan')
    destinations.add(key)
    if destination.exists() and not os.path.samefile(source, destination):
      raise ValueError(f'Destination collision: {destination}')
  by_source = {i['source']: i for i in plan['items']}
  for item in plan['items']:
    if Path(item['source']).suffix.lower() == '.idx':
      other = by_source[str(Path(item['source']).with_suffix('.sub'))]
      if Path(item['mapping']['destination']).with_suffix('.sub') != Path(other['mapping']['destination']):
        raise ValueError('VobSub destination names must match')


def apply(store, config, plan):
  from .cli import execute
  key = digest(plan)
  saved = store.db.execute("SELECT detail FROM events WHERE category='subtitle-backfill-approved'").fetchall()
  previous = next((json.loads(r[0]) for r in saved if json.loads(r[0])['digest'] == key), None)
  if previous:
    batch = previous['batch']
  else:
    validate(store, config, plan)
    store.backup(config['localBackups'], force=True)
    now, manifest = time.time(), []
    # Publish decisions and their batch together, so interrupted approval cannot
    # leave accepted-but-unbatched companions. Original exclusions are retained.
    with store.db:
      for item in plan['items']:
        revision = item['revision']
        if item.get('inventorySignature', item['signature']) != item['signature']:
          revision = store.db.execute('''INSERT INTO revisions(file_id,signature,first_seen,last_seen,observations)
            VALUES (?,?,?,?,1)''', (item['fileId'], packed(item['signature']), now, now)).lastrowid
          store.db.execute('UPDATE files SET current_revision=? WHERE id=?', (revision, item['fileId']))
          store.event('subtitle-mount-revalidated', {'oldRevision': item['revision'], 'newRevision': revision,
            'oldSignature': item['inventorySignature'], 'signature': item['signature']}, item['fileId'])
        proposal = store.db.execute('INSERT INTO proposals(revision_id,mapping,created) VALUES (?,?,?)',
          (revision, packed(item['mapping']), now)).lastrowid
        store.db.execute('INSERT INTO decisions(revision_id,proposal_id,action,reason,created) VALUES (?,?,?,?,?)',
          (revision, proposal, 'accept', 'User authorized subtitle backfill from verified movie/TV mappings', now))
        manifest.append({k: item[k] for k in ('source', 'signature', 'mapping')} | {'proposal': proposal, 'revision': revision})
      batch = store.db.execute('INSERT INTO batches(manifest,digest,approved,transfer_confirmed) VALUES (?,?,?,?)',
        (packed(manifest), digest(manifest), now, now)).lastrowid
      for item in manifest:
        store.db.execute("INSERT INTO operations(batch_id,proposal_id,status) VALUES (?,?,'approved')", (batch, item['proposal']))
      store.event('subtitle-backfill-approved', {'digest': key, 'batch': batch, 'skipped': plan.get('skipped', [])})
  print(f'Subtitle batch: {batch}', flush=True)
  execute(store, config, batch, verify_hashes=True)
  # Recheck every link after completion, including when resuming a finished plan.
  for item in plan['items']:
    if not os.path.samefile(contained(store.root, item['source']), contained(config['media'], item['mapping']['destination'])):
      raise ValueError('Completed subtitle is not a source hardlink')
  print(f'Verified {len(plan["items"])} subtitle hardlinks in batch {batch}', flush=True)
  return batch


def main():
  from .cli import mount_check
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('plan')
  parser.add_argument('--apply', action='store_true')
  parser.add_argument('--config', default='/etc/media-import.json')
  args = parser.parse_args()
  config = json.loads(Path(args.config).read_text())
  plan = json.loads(Path(args.plan).read_text())
  mount_check(config)
  directory = Path(config['database']).parent
  with (directory / 'coord.lock').open('a') as coordinator, (directory / 'audit.lock').open('a') as lock:
    fcntl.flock(coordinator, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    store = Store(config['database'], config['source'], readonly=not args.apply)
    try:
      if args.apply:
        apply(store, config, plan)
      else:
        validate(store, config, plan)
        print(f'Validated {len(plan["items"])} subtitle mappings; no imports performed')
    finally:
      store.db.close()


if __name__ == '__main__':
  main()
