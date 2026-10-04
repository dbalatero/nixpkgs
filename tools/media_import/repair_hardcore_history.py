"""Audited, resumable correction of the early generic-album Hardcore History import."""
import json
import os
import time
from pathlib import Path

from .apps import Apps
from .store import contained, digest, packed, signature, validate_book_mappings


def repair(store, config, batch_id):
  from .cli import apply_batch, execute, hardcore_history_mapping, preflight_item
  for row in store.db.execute("SELECT detail FROM events WHERE category='hardcore-history-repair-complete'"):
    if json.loads(row[0])["originalBatch"] == batch_id:
      print("Hardcore History repair already completed; nothing changed.")
      return
  category = f"hardcore-history-repair-{batch_id}"
  saved = store.db.execute("SELECT detail FROM events WHERE category=? ORDER BY id DESC LIMIT 1", (category,)).fetchone()
  api = Apps(config).api("audiobookshelf")
  if saved:
    plan = json.loads(saved[0])
  else:
    original = store.db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not original:
      raise ValueError("Unknown batch")
    manifest = json.loads(original["manifest"])
    if digest(manifest) != original["digest"]:
      raise ValueError("Original batch digest mismatch")
    items = []
    for item in manifest:
      mapping = item["mapping"]
      if mapping.get("entityPath") != "spoken-word/Dan Carlin/dancarlin.com":
        continue
      if mapping["kind"] != "spoken-word" or "hardcore history" not in item["source"].lower():
        raise ValueError("Repair source is not the expected Hardcore History collection")
      op = store.db.execute("SELECT * FROM operations WHERE proposal_id=?", (item["proposal"],)).fetchone()
      source, old_path = preflight_item(store, config, item, op)
      new_mapping = hardcore_history_mapping(item["source"])
      new_path = contained(config["media"], new_mapping["destination"])
      if new_path.exists():
        raise ValueError(f"Unrecorded destination already exists: {new_path}")
      if old_path.exists() and not os.path.samefile(source, old_path):
        raise ValueError("Old destination is not a source hardlink")
      items.append({"source": item["source"], "oldDestination": mapping["destination"],
        "oldOperation": dict(op), "oldRevision": item["revision"],
        "signature": signature(source), "mapping": new_mapping})
    if not items:
      raise ValueError("No generic-album Hardcore History mappings in this batch")
    validate_book_mappings(items)
    print(f"Repairing {len(items)} episodes as individual entries in Hardcore History.", flush=True)
    store.backup(config["localBackups"])
    api.call("backups", "POST", {})
    now = time.time()
    new_manifest = []
    # All new records and supersession checkpoints commit together. Old manifests,
    # proposals, decisions, and operation snapshots remain available for audit.
    with store.db:
      for item in items:
        old_revision = store.db.execute("SELECT * FROM revisions WHERE id=?", (item["oldRevision"],)).fetchone()
        rev = store.db.execute("INSERT INTO revisions(file_id,signature,first_seen,last_seen,observations,probe) VALUES (?,?,?,?,?,?)",
          (old_revision["file_id"], packed(item["signature"]), now, now, 1, old_revision["probe"])).lastrowid
        store.db.execute("UPDATE files SET current_revision=? WHERE id=?", (rev, old_revision["file_id"]))
        proposal = store.db.execute("INSERT INTO proposals(revision_id,mapping,created) VALUES (?,?,?)", (rev, packed(item["mapping"]), now)).lastrowid
        store.db.execute("INSERT INTO decisions(revision_id,proposal_id,action,reason,created) VALUES (?,?,'accept',?,?)",
          (rev, proposal, "User requested separate Hardcore History episodes grouped as a numbered series", now))
        store.db.execute("UPDATE operations SET status='superseded',error=NULL WHERE id=?", (item["oldOperation"]["id"],))
        new_manifest.append({"proposal": proposal, "revision": rev, "source": item["source"], "signature": item["signature"], "mapping": item["mapping"]})
      new_batch = store.db.execute("INSERT INTO batches(manifest,digest,approved,transfer_confirmed) VALUES (?,?,?,?)",
        (packed(new_manifest), digest(new_manifest), now, original["transfer_confirmed"])).lastrowid
      for item, entry in zip(items, new_manifest):
        item["newOperation"] = store.db.execute("INSERT INTO operations(batch_id,proposal_id,status) VALUES (?,?,'approved')", (new_batch, entry["proposal"])).lastrowid
      plan = {"originalBatch": batch_id, "newBatch": new_batch, "items": items}
      store.event(category, plan)
    store.backup(config["localBackups"])
  apply_batch(store, config, plan["newBatch"])
  # Remove only the obsolete hardlink names, after every replacement is verified.
  for item in plan["items"]:
    source = contained(store.root, item["source"])
    old = contained(config["media"], item["oldDestination"])
    new = contained(config["media"], item["mapping"]["destination"])
    op = store.db.execute("SELECT * FROM operations WHERE id=?", (item["newOperation"],)).fetchone()
    expected = json.loads(op["verified_signature"]) if op["verified_signature"] else None
    observed = signature(source)
    if op["status"] != "verified" or not os.path.samefile(source, new) or observed[:2] != expected[:2] or observed[3:] != expected[3:]:
      raise ValueError("Replacement is not verified or source changed; refusing cleanup")
    if old.exists():
      if not os.path.samefile(source, old):
        raise ValueError("Obsolete destination was replaced; refusing cleanup")
      store.event("repair-unlink-intent", {"oldDestination": str(old), "replacement": str(new)})
      store.db.commit()
      old.unlink()
    # Unlinking changes ctime; keep the verified baseline consistent. Repeating
    # this checkpoint after interruption is safe with the identity checks above.
    store.db.execute("UPDATE operations SET verified_signature=? WHERE id=?", (packed(signature(source)), item["newOperation"]))
    store.db.commit()
  old_folder = contained(config["media"], "spoken-word/Dan Carlin/dancarlin.com")
  if old_folder.exists():
    old_folder.rmdir()  # Refuse to remove unexpected contents.
  for library in api.call("libraries")["libraries"]:
    if not any(f["fullPath"] == str(Path(config["media"]) / "spoken-word") for f in library["folders"]):
      continue
    for item in api.call(f"libraries/{library['id']}/items", limit=1000)["results"]:
      if item["path"] == str(old_folder):
        snapshot = api.call(f"items/{item['id']}", expanded=1, include="progress")
        store.event("repair-obsolete-abs-item", snapshot)
        store.db.commit()
        api.call(f"items/{item['id']}", "DELETE", hard=0)
  execute(store, config, plan["newBatch"], verify_only=True)
  apply_batch(store, config, batch_id)
  store.event("hardcore-history-repair-complete", {"originalBatch": batch_id, "repairBatch": plan["newBatch"]})
  store.db.commit()
  store.backup(config["localBackups"])
  print(f"Repair complete: batch {plan['newBatch']}; original batch {batch_id} also finished.")
