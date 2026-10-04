"""Apply Nix's download-client declarations through the supported Servarr APIs."""
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def call(app, endpoint, method="GET", body=None):
  headers = {"X-Api-Key": Path(app["keyFile"]).read_text().strip(), "Content-Type": "application/json"}
  request = urllib.request.Request(app["url"] + "/" + endpoint, headers=headers, method=method,
    data=None if body is None else json.dumps(body).encode())
  try:
    with urllib.request.urlopen(request, timeout=30) as response:
      data = response.read()
      return json.loads(data) if data else None
  except urllib.error.HTTPError as error:
    raise RuntimeError(f"Servarr {method} {endpoint}: HTTP {error.code}") from None


def configure(settings):
  for name, desired in settings["torrentClients"].items():
    app = settings["apps"][name]
    clients = call(app, "downloadclient")
    matches = [client for client in clients if client["name"] == desired["name"]]
    if len(matches) > 1:
      raise RuntimeError(f"Duplicate managed download clients in {name}")
    current = matches[0] if matches else None
    if current and current["implementation"] != "QBittorrent":
      raise RuntimeError(f"Managed client name belongs to another implementation in {name}")
    client = current or next(item for item in call(app, "downloadclient/schema") if item["implementation"] == "QBittorrent")
    client.update(name=desired["name"], enable=True, priority=1,
      removeCompletedDownloads=False, removeFailedDownloads=False)
    values = desired["fields"]
    if set(values) - {field["name"] for field in client["fields"]}:
      raise RuntimeError(f"Unexpected qBittorrent schema in {name}")
    for field in client["fields"]:
      if field["name"] in values:
        field["value"] = values[field["name"]]
    call(app, "downloadclient/test", "POST", client)
    if current:
      call(app, f"downloadclient/{client['id']}", "PUT", client)
    else:
      call(app, "downloadclient", "POST", client)
    print(f"{name}: qBittorrent connection tested and configured", flush=True)


if __name__ == "__main__":
  settings = json.loads(Path("/etc/media-import.json").read_text())
  for attempt in range(10):
    try:
      configure(settings)
      break
    except (OSError, RuntimeError):
      if attempt == 9:
        raise
      time.sleep(5)
