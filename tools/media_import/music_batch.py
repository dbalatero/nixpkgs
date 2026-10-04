"""Copy an approved album, register its tracks in one command, checkpoint each file."""
import json
from pathlib import Path

from .music_copy import copy_file, owned
from .store import packed, signature


def album_key(item):
  mapping = item['mapping']
  identity = mapping['identity']
  return tuple(identity.get(k) for k in ('foreignArtistId', 'foreignAlbumId', 'foreignReleaseId')) + (mapping['entityPath'],)


def execute_album(store, config, items, apps):
  from .cli import audit_lock
  with audit_lock(store.path.parent / 'music-catalog.lock'):
    _execute_album(store, config, items, apps)


def _execute_album(store, config, items, apps):
  from .cli import preflight_item
  pending = []
  active = None
  try:
    for item in items:
      active = store.db.execute('SELECT * FROM operations WHERE proposal_id=?', (item['proposal'],)).fetchone()
      if active['status'] == 'verified':
        continue
      source, destination = preflight_item(store, config, item, active)
      observed = signature(source)
      record = json.loads(active['app_record']) if active['app_record'] else None
      if record is None:
        record = apps.prepare(item['mapping'], Path(config['media']))
        if any(path != str(destination) for path in record.get('existingPaths', [])):
          raise ValueError('App already has a file for this identity; replacement is prohibited')
        store.db.execute("UPDATE operations SET app_record=?,status='prepared' WHERE id=?", (packed(record), active['id']))
        store.db.commit()
      if signature(source) != observed:
        raise ValueError('Source changed during music preparation')
      copy_file(store, active['id'], source, destination)
      owned(store, active['id'], source, destination)
      if signature(source) != observed:
        raise ValueError('Source changed during music copy')
      record['expectedPath'] = str(destination)
      before = active['before_hash'] or store.cached_hash(item['revision'], observed)
      store.db.execute("UPDATE operations SET status='linked',verified_signature=?,app_record=?,before_hash=? WHERE id=?",
        (packed(observed), packed(record), before, active['id']))
      store.db.commit()
      pending.append((active, item, source, destination, observed, record, before))
    if not pending:
      return
    ids = [entry[5]['trackId'] for entry in pending]
    if len(set(ids)) != len(ids):
      raise ValueError('Album batch maps multiple files to the same track')
    print(f"Registering {len(pending)} tracks: {items[0]['mapping']['identity'].get('title', 'album')}…", flush=True)
    apps.scan_music([entry[5] for entry in pending])
    for active, item, source, destination, observed, record, before in pending:
      owned(store, active['id'], source, destination)
      record = apps.verify(record, item['mapping'], destination)
      if signature(source) != observed:
        raise ValueError('Source changed during music import')
      store.db.execute("UPDATE operations SET status='verified',app_record=?,error=NULL WHERE id=?", (packed(record), active['id']))
      store.event('verified', {'operation':active['id'], 'sha256':before, 'content_checked':False, 'destination':str(destination), 'mode':'copy'})
      store.db.commit()
      print(f"Verified: {item['source']} -> {destination}", flush=True)
  except Exception as exc:
    if active:
      store.db.execute('UPDATE operations SET error=? WHERE id=?', (str(exc), active['id']))
      store.event('operation-failed', {'operation':active['id'], 'error':str(exc)})
      store.db.commit()
    raise
