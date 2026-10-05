"""Reconcile Usenet integrations; never print API responses or credentials."""
import copy
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def request_json(url, headers=None, method="GET", body=None):
  request = urllib.request.Request(url, headers=headers or {}, method=method,
    data=None if body is None else json.dumps(body).encode())
  try:
    with urllib.request.urlopen(request, timeout=45) as response:
      data = response.read()
      return json.loads(data) if data else None
  except Exception as error:
    # URLs and validation responses can contain keys, passwords, and NZB URLs.
    raise RuntimeError(f"API request failed ({type(error).__name__})") from None


def arr(app, endpoint, method="GET", body=None):
  return request_json(app["url"] + "/" + endpoint,
    {"X-Api-Key": app["key"], "Content-Type": "application/json"}, method, body)


def reconcile(app, endpoint, name, implementation, fields, attributes, preset=None):
  existing = arr(app, endpoint)
  matches = [item for item in existing if item["name"].casefold() == name.casefold()]
  if len(matches) > 1:
    raise RuntimeError(f"Duplicate managed {endpoint}: {name}")
  current = matches[0] if matches else None
  if current and current["implementation"] != implementation:
    raise RuntimeError(f"Managed {endpoint} name has a different implementation")
  if current:
    desired = copy.deepcopy(current)
  else:
    schemas = arr(app, endpoint + "/schema")
    desired = copy.deepcopy(next(item for item in schemas
      if item["implementation"] == implementation and (preset is None or item["name"] == preset)))
  if set(fields) - {field["name"] for field in desired["fields"]}:
    raise RuntimeError(f"Unsupported {implementation} schema")
  desired.update(attributes)
  desired["name"] = name
  for field in desired["fields"]:
    if field["name"] in fields:
      field["value"] = fields[field["name"]]
  arr(app, endpoint + "/test", "POST", desired)
  if desired != current:
    arr(app, f"{endpoint}/{current['id']}" if current else endpoint,
      "PUT" if current else "POST", desired)
  return desired != current


def configure(settings, credentials):
  secrets = json.loads((credentials / "usenet").read_text())
  sab_key = (credentials / "sab-api").read_text().strip()
  apps = copy.deepcopy(settings["apps"])
  apps["prowlarr"] = copy.deepcopy(settings["prowlarr"])
  for app in apps.values():
    app["key"] = ET.parse(credentials / app["credential"]).getroot().findtext("ApiKey")
    if not app["key"]:
      raise RuntimeError("Application key is not initialized")
  common = {"host": "127.0.0.1", "port": settings["sab"]["port"], "useSsl": False, "apiKey": sab_key}
  for name, app in apps.items():
    category = {"category": "prowlarr"} if name == "prowlarr" else {
      app["category"] + "Category": app["category"]}
    attrs = {"enable": True, "priority": 1}
    if name != "prowlarr":
      attrs.update(removeCompletedDownloads=True, removeFailedDownloads=True)
    reconcile(app, "downloadclient", "SABnzbd", "Sabnzbd", common | category, attrs)
    if name != "prowlarr":
      policy = arr(app, "config/downloadclient")
      desired = policy | {"enableCompletedDownloadHandling": True, "autoRedownloadFailed": True}
      if policy != desired:
        arr(app, "config/downloadclient", "PUT", desired)
      profiles = arr(app, "delayprofile")
      default = next(p for p in profiles if p["id"] == 1)
      desired = default | {"enableUsenet": True, "enableTorrent": True, "preferredProtocol": "usenet"}
      if default != desired:
        arr(app, "delayprofile/1", "PUT", desired)
    print(f"{name}: SABnzbd tested and configured", flush=True)
  reconcile(apps["prowlarr"], "indexer", "NinjaCentral", "Newznab",
    {"baseUrl": "https://ninjacentral.co.za", "apiPath": "/api", "apiKey": secrets["ninjacentral_api_key"]},
    {"enable": True, "appProfileId": 1, "priority": settings["indexerPriority"]}, preset="NinjaCentral")
  arr(apps["prowlarr"], "command", "POST", {"name": "ApplicationIndexerSync"})
  print("NinjaCentral tested and configured; application indexer sync requested", flush=True)


def sab(settings, key, **params):
  # Submit the API key in the POST body, never in the URL or command line.
  data = urllib.parse.urlencode({"apikey": key, "output": "json", **params}).encode()
  request = urllib.request.Request(settings["sab"]["url"] + "/api", data=data)
  try:
    with urllib.request.urlopen(request, timeout=30) as response:
      result = json.load(response)
  except Exception as error:
    raise RuntimeError(f"SABnzbd API failed ({type(error).__name__})") from None
  if result.get("status") is False:
    raise RuntimeError("SABnzbd rejected the request")
  return result


def retain_history(settings, credentials, now=None):
  key = (credentials / "sab-api").read_text().strip()
  cutoff = (time.time() if now is None else now) - 30 * 86400
  expired = []
  for archive in (0, 1):
    start = 0
    while True:
      slots = sab(settings, key, mode="history", start=start, limit=100, archive=archive)["history"]["slots"]
      for slot in slots:
        if slot["status"] in ("Completed", "Failed") and float(slot["completed"]) < cutoff:
          expired.append((slot["nzo_id"], archive))
      if len(slots) < 100:
        break
      start += len(slots)
  removed = 0
  for job, archive in expired:
    # Recheck each job in case it was retried while we were reading history.
    slots = sab(settings, key, mode="history", nzo_ids=job, limit=100, archive=archive)["history"]["slots"]
    if len(slots) == 1 and slots[0]["status"] in ("Completed", "Failed") and float(slots[0]["completed"]) < cutoff:
      sab(settings, key, mode="history", name="delete", value=job, del_files=0, archive=0)
      removed += 1
  print(f"Expired {removed} old job reports; downloaded files retained", flush=True)


if __name__ == "__main__":
  try:
    settings = json.loads(Path(sys.argv[1]).read_text())
    credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
    if "--retain-history" in sys.argv:
      retain_history(settings, credentials)
    else:
      configure(settings, credentials)
  except Exception as error:
    raise SystemExit(f"Usenet configuration failed ({type(error).__name__})") from None
