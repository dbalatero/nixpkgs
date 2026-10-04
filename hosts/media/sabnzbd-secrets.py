"""Render runtime secrets without placing credentials in the Nix store."""
import json
import os
from pathlib import Path
import secrets
from configobj import ConfigObj


def prepare(credentials, state, destination):
  required = ("eweka_username", "eweka_password", "ninjacentral_api_key")
  if any(not isinstance(credentials.get(k), str) or not credentials[k].strip() for k in required):
    raise ValueError("Missing Usenet credential")
  os.umask(0o077)
  keys = {}
  for name in ("api-key", "nzb-key"):
    path = state / name
    if not path.exists():
      with path.open("x") as output:
        output.write(secrets.token_hex(32))
    keys[name] = path.read_text().strip()
    if not keys[name]:
      raise ValueError("Empty SABnzbd key")
  conf = ConfigObj(encoding="utf-8")
  conf["misc"] = {"api_key": keys["api-key"], "nzb_key": keys["nzb-key"]}
  conf["servers"] = {"Eweka": {
    "username": credentials["eweka_username"], "password": credentials["eweka_password"]}}
  with destination.open("wb") as output:
    conf.write(output)


if __name__ == "__main__":
  try:
    credentials = json.loads((Path(os.environ["CREDENTIALS_DIRECTORY"]) / "usenet").read_text())
    prepare(credentials, Path("/var/lib/sabnzbd"), Path("/run/sabnzbd/secrets.ini"))
  except Exception as error:
    raise SystemExit(f"SABnzbd credential setup failed ({type(error).__name__})") from None
