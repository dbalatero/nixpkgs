"""Prepare runtime credentials and merge Nix-managed categories before startup."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys


profile = Path(sys.argv[1])
desired = json.loads(Path(sys.argv[2]).read_text())
os.umask(0o077)
password_file = profile / "webui-password"
if not password_file.exists():
  password_file.write_text(secrets.token_urlsafe(32) + "\n")
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha512", password_file.read_text().strip().encode(), salt, 100000)
encoded = base64.b64encode(salt).decode() + ":" + base64.b64encode(digest).decode()
config_file = profile / "qBittorrent/config/qBittorrent.conf"
text = config_file.read_text()
text = text.replace("[Preferences]\n", "[Preferences]\nWebUI\\Password_PBKDF2=\"@ByteArray(" + encoded + ")\"\n")
config_file.write_text(text)
categories_file = config_file.parent / "categories.json"
categories = json.loads(categories_file.read_text()) if categories_file.exists() else {}
categories.update(desired)
categories_file.write_text(json.dumps(categories, indent=2) + "\n")
for category in desired.values():
  directory = Path(category["save_path"])
  if not directory.is_dir() or not os.access(directory, os.W_OK):
    raise SystemExit(f"Torrent directory missing or not writable: {directory}")
