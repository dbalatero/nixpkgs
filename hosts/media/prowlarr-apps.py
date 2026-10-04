"""Reconcile Nix-declared Prowlarr applications without exposing API keys."""
import copy
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def api_key(path):
  key = ET.parse(path).getroot().findtext("ApiKey")
  if not key:
    raise RuntimeError("Application API key not initialized")
  return key


def call(settings, endpoint, method="GET", body=None):
  request = urllib.request.Request(
    settings["url"] + "/api/v1/" + endpoint,
    headers={"X-Api-Key": api_key(settings["configXml"]),
      "Content-Type": "application/json"},
    method=method, data=None if body is None else json.dumps(body).encode())
  try:
    with urllib.request.urlopen(request, timeout=20) as response:
      data = response.read()
      return json.loads(data) if data else None
  except urllib.error.HTTPError as error:
    # Validation responses can contain credentials; never log their bodies.
    raise RuntimeError(f"Prowlarr {method} {endpoint}: HTTP {error.code}") from None


def configure(settings):
  schemas = call(settings, "applications/schema")
  applications = call(settings, "applications")
  for name, desired in settings["apps"].items():
    implementation = desired["implementation"]
    matches = [app for app in applications if app["name"] == implementation]
    if len(matches) > 1:
      raise RuntimeError(f"Duplicate managed application: {implementation}")
    current = matches[0] if matches else None
    if current and current["implementation"] != implementation:
      raise RuntimeError(f"Managed name belongs to another application: {implementation}")
    app = copy.deepcopy(current or next(
      item for item in schemas if item["implementation"] == implementation))
    values = {"baseUrl": desired["url"], "prowlarrUrl": settings["url"],
      "apiKey": api_key(desired["configXml"])}
    if set(values) - {field["name"] for field in app["fields"]}:
      raise RuntimeError(f"Unexpected application schema: {implementation}")
    app.update(name=implementation, syncLevel="fullSync")
    for field in app["fields"]:
      if field["name"] in values:
        field["value"] = values[field["name"]]
    call(settings, "applications/test", "POST", app)
    if current:
      if app != current:
        call(settings, f"applications/{app['id']}", "PUT", app)
    else:
      call(settings, "applications", "POST", app)
    print(f"{name}: Prowlarr connection tested and configured", flush=True)


def main():
  settings = json.loads(Path(sys.argv[1]).read_text())
  for attempt in range(12):
    try:
      configure(settings)
      return
    except (OSError, RuntimeError, ET.ParseError, StopIteration) as error:
      if attempt == 11:
        # Exception type only: even network errors may contain sensitive data.
        raise SystemExit(f"Prowlarr application setup failed ({type(error).__name__})") from None
      time.sleep(5)


if __name__ == "__main__":
  main()
