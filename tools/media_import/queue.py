"""Durable queue for user-approved music batches; no automatic approvals."""
import json
import time


def enqueue(store, batch):
  row = store.db.execute('SELECT manifest FROM batches WHERE id=?', (batch,)).fetchone()
  if not row or not all(x['mapping']['kind'] == 'music' for x in json.loads(row[0])):
    raise ValueError('Background queue accepts approved music-only batches')
  with store.db:
    store.db.execute("INSERT OR IGNORE INTO import_jobs(batch_id,status,updated) VALUES (?,'queued',?)", (batch,time.time()))
    store.event('import-queued', {'batch':batch})
  print(f'Queued batch {batch}. You can review the next music batch now. Check progress with: media-import queue')


def work(store, config):
  from .cli import apply_batch
  while True:
    job = store.db.execute("SELECT batch_id FROM import_jobs WHERE status IN ('queued','running') ORDER BY batch_id LIMIT 1").fetchone()
    if job is None:
      return
    batch = job[0]
    store.db.execute("UPDATE import_jobs SET status='running',error=NULL,updated=? WHERE batch_id=?", (time.time(),batch))
    store.db.commit()
    try:
      apply_batch(store, config, batch)
    except Exception as exc:
      finish(store,batch,'failed',str(exc))
      print(f'Batch {batch} needs attention: {exc}', flush=True)
    else:
      finish(store,batch,'complete')


def finish(store, batch, status, error=None):
  store.db.execute('UPDATE import_jobs SET status=?,error=?,updated=? WHERE batch_id=?', (status,error,time.time(),batch))
  store.db.commit()


def show(store):
  rows = store.db.execute('SELECT * FROM import_jobs ORDER BY batch_id DESC LIMIT 20').fetchall()
  if not rows:
    print('No queued music imports.')
  for row in rows:
    total,done = store.db.execute("SELECT count(*),sum(status IN ('verified','superseded')) FROM operations WHERE batch_id=?",(row['batch_id'],)).fetchone()
    done = done or 0
    print(f"Batch {row['batch_id']}: {row['status']} — {done}/{total} files ({100*done/total if total else 100:.0f}%)")
    if row['error']:
      print(f"  {row['error']}\n  Resume: media-import apply {row['batch_id']}")
