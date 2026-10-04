"""Move the legacy spoken-word library while retaining audit and app identities."""
import json
import time
from pathlib import Path

from .apps import Apps
from .store import contained, packed


def migrate(store, config):
  if store.db.execute("SELECT 1 FROM events WHERE category='podcasts-library-migration-complete'").fetchone():
    print("Podcasts migration already completed; nothing changed.")
    return
  api = Apps(config).api("audiobookshelf")
  old, new = (contained(config["media"], name) for name in ("spoken-word", "podcasts"))
  category = "podcasts-library-migration"
  saved = store.db.execute("SELECT detail FROM events WHERE category=? ORDER BY id LIMIT 1", (category,)).fetchone()
  if saved:
    plan = json.loads(saved[0])
  else:
    libraries = [lib for lib in api.call("libraries")["libraries"] if any(f["fullPath"] == str(old) for f in lib["folders"])]
    if len(libraries) != 1 or not old.is_dir():
      raise ValueError("Expected exactly one legacy library and its folder")
    if new.exists() and (not new.is_dir() or any(new.iterdir())):
      raise ValueError("New podcasts folder must be absent or empty")
    library = libraries[0]
    if len(library["folders"]) != 1:
      raise ValueError("Unexpected extra library folders; review migration")
    snapshot = api.call(f"libraries/{library['id']}/items", limit=1000)
    if snapshot["total"] > 1000:
      raise ValueError("Migration snapshot requires pagination")
    items = [api.call(f"items/{item['id']}", expanded=1) for item in snapshot["results"]]
    plan = {"library": library, "items": items}
    store.backup(config["localBackups"])
    api.call("backups", "POST", {})
    store.event(category, plan)
    store.db.commit()
  if old.exists():
    if new.exists() and any(new.iterdir()):
      raise ValueError("Refusing to merge populated library roots")
    old.rename(new)
  if not new.is_dir():
    raise ValueError("Relocated library is missing")
  library_id = plan["library"]["id"]
  current = api.call(f"libraries/{library_id}")
  folders = current["folders"]
  if not any(f["fullPath"] == str(new) for f in folders):
    # Keep the old folder registered until the scanner has moved each existing
    # item by inode. Removing a folder first would delete its catalog records.
    folders = folders + [{"fullPath": str(new)}]
  api.call(f"libraries/{library_id}", "PATCH", {"name": "Podcasts", "folders": folders})
  # A separate recorded relocation interprets immutable historical paths. It
  # does not rewrite old proposals/manifests or invalidate their digests.
  with store.db:
    store.db.execute("INSERT OR REPLACE INTO meta VALUES ('library_relocations', ?)", (packed([["spoken-word", "podcasts"]]),))
    store.db.execute("UPDATE files SET kind='podcast' WHERE kind='spoken-word'")
  api.call(f"libraries/{library_id}/scan", "POST", {})
  expected = {item["id"]: str(new / Path(item["path"]).relative_to(old)) for item in plan["items"]}
  deadline = time.monotonic() + 120
  while time.monotonic() < deadline:
    items = api.call(f"libraries/{library_id}/items", limit=1000)["results"]
    observed = {item["id"]: item["path"] for item in items}
    if all(observed.get(key) == path for key, path in expected.items()):
      break
    time.sleep(2)
  else:
    raise ValueError("Scan has not preserved all item IDs at the new paths; migration saved for investigation")
  current = api.call(f"libraries/{library_id}")
  new_folder = next(f for f in current["folders"] if f["fullPath"] == str(new))
  for original in plan["items"]:
    found = api.call(f"items/{original['id']}", expanded=1)
    if found.get("folderId", found.get("libraryFolderId")) != new_folder["id"]:
      raise ValueError("Item is not assigned to the new library folder; refusing to remove old folder")
    metadata = original["media"]["metadata"]
    api.call(f"items/{original['id']}/media", "PATCH", {"metadata": {
      key: metadata[key] for key in ("title", "authors", "series", "narrators") if key in metadata}})
  api.call(f"libraries/{library_id}", "PATCH", {"folders": [new_folder]})
  for op in store.db.execute("SELECT * FROM operations WHERE status='verified'").fetchall():
    record = json.loads(op["app_record"]) if op["app_record"] else None
    if record and record.get("app") == "audiobookshelf":
      updated = store.relocate_record(record, config["media"])
      store.db.execute("UPDATE operations SET app_record=? WHERE id=?", (packed(updated), op["id"]))
  store.event("podcasts-library-migration-complete", {"libraryId": library_id, "preservedItems": len(expected)})
  store.db.commit()
  store.backup(config["localBackups"])
  print(f"Podcasts library moved; {len(expected)} item IDs preserved.")
