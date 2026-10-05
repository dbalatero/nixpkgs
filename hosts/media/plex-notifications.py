"""Reconcile Nix-owned Plex connections using runtime-only credentials."""
import copy
import json
import os
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET


def call(app, key, endpoint, method="GET", body=None):
  request = urllib.request.Request(app["url"] + "/" + endpoint,
    headers={"X-Api-Key": key, "Content-Type": "application/json"},
    method=method, data=None if body is None else json.dumps(body).encode())
  with urllib.request.urlopen(request, timeout=20) as response:
    data = response.read()
    return json.loads(data) if data else None


def configure(settings):
  credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
  token = ET.parse(settings["plexPreferences"]).getroot().get("PlexOnlineToken")
  if not token:
    raise RuntimeError("Plex must be claimed before configuring notifications")
  for name, app in settings["apps"].items():
    key = ET.parse(credentials / f"{name}.xml").getroot().findtext("ApiKey")
    if not key:
      raise RuntimeError("Application API key not initialized")
    notifications = call(app, key, "notification")
    matches = [n for n in notifications if n["name"] == "Plex (Nix)"]
    if len(matches) > 1:
      raise RuntimeError("Duplicate managed Plex connections")
    current = matches[0] if matches else None
    if current and current["implementation"] != "PlexServer":
      raise RuntimeError("Managed name belongs to another implementation")
    schema = next(n for n in call(app, key, "notification/schema")
      if n["implementation"] == "PlexServer")
    notification = copy.deepcopy(current or schema)
    notification.update(name="Plex (Nix)", tags=[])
    # Own the event selection, without enabling unrelated alerts or grabs.
    for field in schema:
      if field.startswith("on") and isinstance(schema[field], bool):
        notification[field] = field in app["events"]
    for event in app["events"]:
      if not schema.get("supports" + event[0].upper() + event[1:]):
        raise RuntimeError("Required Plex event unsupported")
    values = {"host": settings["host"], "port": settings["port"],
      "useSsl": False, "urlBase": "", "authToken": token,
      "updateLibrary": True, "mapFrom": "", "mapTo": ""}
    if set(values) - {f["name"] for f in notification["fields"]}:
      raise RuntimeError("Unexpected Plex connection schema")
    for field in notification["fields"]:
      if field["name"] in values:
        field["value"] = values[field["name"]]
    call(app, key, "notification/test", "POST", notification)
    if current:
      if notification != current:
        call(app, key, f"notification/{current['id']}", "PUT", notification)
    else:
      call(app, key, "notification", "POST", notification)
    print(f"{name}: Plex connection tested; events: {', '.join(app['events'])}", flush=True)


if __name__ == "__main__":
  try:
    configure(json.loads(Path(sys.argv[1]).read_text()))
  except Exception as error:
    # API errors can echo credentials. Never log response bodies or URLs.
    raise SystemExit(f"Plex connection setup failed ({type(error).__name__})") from None
