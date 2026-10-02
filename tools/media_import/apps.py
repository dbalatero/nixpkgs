"""Supported HTTP interfaces only; never access an application's SQLite tables."""
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


class API:
  def __init__(self, settings):
    self.settings = settings
    self.url = settings["url"].rstrip("/")
    parsed = urllib.parse.urlparse(self.url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
      raise ValueError("Import APIs must use loopback; use an SSH tunnel for remote review")

  def call(self, endpoint, method="GET", body=None, **query):
    settings = self.settings
    if settings.get("keyFile") and Path(settings["keyFile"]).exists():
      key = Path(settings["keyFile"]).read_text().strip()
    elif settings.get("configXml"):
      key = ET.parse(settings["configXml"]).getroot().findtext("ApiKey")
    else:
      raise ValueError("Missing runtime API credential; complete app initialization")
    if not key:
      raise ValueError("API credential is empty")
    headers = {"Content-Type": "application/json"}
    headers["Authorization" if settings.get("bearer") else "X-Api-Key"] = "Bearer " + key if settings.get("bearer") else key
    url = self.url + "/" + endpoint
    if query:
      url += "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
      with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
        if not data:
          return None
        return json.loads(data) if response.headers.get_content_type() == "application/json" else data.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
      # Do not echo response bodies or request headers containing credentials.
      raise ValueError(f"API {method} {endpoint} returned HTTP {exc.code}") from None

  def command(self, name, **arguments):
    result = self.call("command", "POST", {"name": name, **arguments})
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
      status = self.call(f"command/{result['id']}")
      if status["status"].lower() == "completed":
        return status
      if status["status"].lower() in {"failed", "aborted", "cancelled"}:
        raise ValueError(f"App command {name} failed; inspect the application log")
      time.sleep(2)
    raise ValueError(f"App command {name} still running; reconcile before retrying")


class Apps:
  def __init__(self, config):
    self.config = config

  def api(self, name):
    return API(self.config["apps"][name])

  def safety(self, name, configure=False):
    api = self.api(name)
    desired = self.config["policy"][name]
    for endpoint, values in desired.items():
      current = api.call(endpoint)
      missing = set(values) - set(current)
      if missing:
        raise ValueError(f"{name} API schema mismatch at {endpoint}: {sorted(missing)}")
      if any(current[k] != v for k, v in values.items()):
        if not configure:
          raise ValueError(f"{name} safety policy drift at {endpoint}; run configure")
        api.call(endpoint, "PUT", {**current, **values})
        observed = api.call(endpoint)
        if any(observed[k] != v for k, v in values.items()):
          raise ValueError(f"{name} did not retain safety settings")
    # Reject acquisition integrations rather than silently changing existing ones.
    for endpoint in ("downloadclient", "indexer", "importlist"):
      if api.call(endpoint):
        raise ValueError(f"{name} has {endpoint} entries; migration-only instance required")
    for profile in api.call("qualityprofile"):
      if profile.get("upgradeAllowed"):
        if not configure:
          raise ValueError(f"{name} quality profile permits upgrades")
        api.call(f"qualityprofile/{profile['id']}", "PUT", {**profile, "upgradeAllowed": False})
    return api.call("system/status")["version"]

  def configure(self):
    for name in ("radarr", "sonarr", "lidarr"):
      print(f"{name}: {self.safety(name, configure=True)}")
      api = self.api(name)
      host = api.call("config/host")
      if host.get("authenticationMethod", "").lower() == "none":
        secret = Path(self.config["database"]).parent / f"{name}.password"
        if not secret.exists():
          secret.write_text(secrets.token_urlsafe(32))
          secret.chmod(0o600)
        host.update(authenticationMethod="forms", authenticationRequired="enabled", username="dbalatero", password=secret.read_text(), passwordConfirmation=secret.read_text())
        api.call("config/host", "PUT", host)
    self.bootstrap_books()

  def bootstrap_books(self):
    settings = self.config["apps"]["audiobookshelf"]
    token_file = Path(settings["keyFile"])
    if token_file.exists():
      self.api("audiobookshelf").call("libraries")
      return
    # This is a declaratively invoked first-start initializer, not a reset of an
    # existing account. Persist the generated secret before creating the user.
    base = settings["url"].removesuffix("/api")
    API(settings)  # Enforce loopback before unauthenticated initialization.
    def request(endpoint, body=None, token=None):
      headers = {"Content-Type": "application/json"}
      if token:
        headers["Authorization"] = "Bearer " + token
      req = urllib.request.Request(base + endpoint, data=json.dumps(body).encode() if body is not None else None, headers=headers)
      with urllib.request.urlopen(req, timeout=60) as response:
        payload = response.read()
        return json.loads(payload) if response.headers.get_content_type() == "application/json" else None
    status = request("/status")
    password = token_file.with_suffix(".password")
    if not password.exists():
      if status["isInit"]:
        raise ValueError("Audiobookshelf already initialized: supply its API token file without resetting the account")
      password.write_text(secrets.token_urlsafe(32))
      password.chmod(0o600)
    credentials = {"username": "dbalatero", "password": password.read_text()}
    if not status["isInit"]:
      request("/init", {"newRoot": credentials})
    login = request("/login", credentials)["user"]
    key = request("/api/api-keys", {"name": "media-import", "userId": login["id"], "isActive": True}, login["accessToken"])
    token_file.write_text(key["apiKey"]["apiKey"])
    token_file.chmod(0o600)
    print("audiobookshelf: runtime account and API credential initialized")

  def lookup(self, kind, query):
    name, resource = {"movie": ("radarr", "movie"), "tv": ("sonarr", "series"), "music": ("lidarr", "album")}[kind]
    api = self.api(name)
    return {"version": api.call("system/status")["version"], "query": query, "results": api.call(resource + "/lookup", term=query)}

  def prepare(self, mapping, media):
    """Register only the approved identity, unmonitored, before creating any links."""
    kind = mapping["kind"]
    identity = mapping["identity"]
    if mapping.get("alternate") or kind == "companion":
      return {"kind": "filesystem"}
    if kind in {"audiobook", "spoken-word"}:
      return self.prepare_books(mapping, media)
    name, resource, foreign = {"movie": ("radarr", "movie", "tmdbId"), "tv": ("sonarr", "series", "tvdbId"), "music": ("lidarr", "artist", "foreignArtistId")}[kind]
    api = self.api(name)
    self.safety(name)
    if api.call("system/status")["version"] != mapping["appVersion"]:
      raise ValueError("App version changed since review; regenerate the proposal")
    profiles = api.call("qualityprofile")
    if not profiles:
      raise ValueError(f"{name} has no quality profiles")
    # The profile is only needed by the API: there are no acquisition connections.
    profile = profiles[0]["id"]
    desired_id = identity[foreign]
    records = [x for x in api.call(resource) if str(x[foreign]) == str(desired_id)]
    library_path = str(media / mapping["entityPath"])
    if records:
      entity = records[0]
      if entity["path"] != library_path or entity.get("monitored"):
        raise ValueError("Existing app identity has a different path or is monitored")
    else:
      term = ("tmdb:" if kind == "movie" else "tvdb:" if kind == "tv" else "lidarr:") + str(desired_id)
      lookup = api.call(resource + "/lookup", term=term)
      exact = [x for x in lookup if str(x[foreign]) == str(desired_id)]
      if len(exact) != 1:
        raise ValueError("Approved provider identity cannot be resolved uniquely")
      entity = exact[0]
      entity.pop("id", None)
      entity.update(path=library_path, qualityProfileId=profile, monitored=False)
      entity["addOptions"] = {"searchForMovie": False, "searchForMissingEpisodes": False, "searchForMissingAlbums": False, "monitor": "none"}
      if kind == "tv":
        entity["seasons"] = [{**s, "monitored": False} for s in entity.get("seasons", [])]
        entity["seasonFolder"] = True
      if kind == "music":
        metadata_profiles = api.call("metadataprofile")
        entity["metadataProfileId"] = metadata_profiles[0]["id"]
      entity = api.call(resource, "POST", entity)
    entity_id = entity["id"]
    record = {"kind": kind, "app": name, "id": entity_id, "version": mapping["appVersion"]}
    if kind == "movie":
      if entity.get("hasFile"):
        record["existingPaths"] = [entity.get("movieFile", {}).get("path", "UNKNOWN EXISTING FILE")]
    elif kind == "tv":
      api.command("RefreshSeries", seriesId=entity_id)
      episodes = api.call("episode", seriesId=entity_id)
      wanted = set(mapping["episodes"])
      selected = [e for e in episodes if e["seasonNumber"] == mapping["season"] and e["episodeNumber"] in wanted]
      if {e["episodeNumber"] for e in selected} != wanted:
        raise ValueError("Approved episode numbers do not exist in Sonarr metadata")
      record["episodeIds"] = [e["id"] for e in selected]
      existing = {f["id"]: f["path"] for f in api.call("episodefile", seriesId=entity_id)}
      record["existingPaths"] = [existing.get(e["episodeFileId"], "UNKNOWN EXISTING FILE") for e in selected if e.get("hasFile")]
    else:
      api.command("RefreshArtist", artistId=entity_id)
      albums = [a for a in api.call("album", artistId=entity_id) if a["foreignAlbumId"] == identity["foreignAlbumId"]]
      if len(albums) != 1:
        raise ValueError("Approved album not available in Lidarr metadata profile")
      album = albums[0]
      selected = [r for r in album["releases"] if r["foreignReleaseId"] == identity["foreignReleaseId"]]
      if len(selected) != 1:
        raise ValueError("Approved MusicBrainz release is not available")
      # Never switch a release for an already imported album.
      existing_tracks = api.call("track", albumId=album["id"])
      if any(t.get("hasFile") for t in existing_tracks) and not selected[0].get("monitored"):
        raise ValueError("Album already has files from a different release")
      album["monitored"] = False
      album["anyReleaseOk"] = False
      for release in album["releases"]:
        release["monitored"] = release["foreignReleaseId"] == identity["foreignReleaseId"]
      api.call(f"album/{album['id']}", "PUT", album)
      tracks = api.call("track", albumId=album["id"])
      matches = [t for t in tracks if t["mediumNumber"] == mapping["disc"] and str(t["trackNumber"]) == str(mapping["track"])]
      if len(matches) != 1:
        raise ValueError("Approved disc/track is not uniquely represented in Lidarr")
      existing = {f["id"]: f["path"] for f in api.call("trackfile", artistId=entity_id)}
      record.update(albumId=album["id"], trackId=matches[0]["id"], existingPaths=[existing.get(matches[0]["trackFileId"], "UNKNOWN EXISTING FILE")] if matches[0].get("hasFile") else [])
    return record

  def prepare_books(self, mapping, media):
    api = self.api("audiobookshelf")
    folder = str(media / ("spoken-word" if mapping["kind"] == "spoken-word" else "audiobooks"))
    libraries = api.call("libraries")["libraries"]
    matches = [lib for lib in libraries if any(f["fullPath"] == folder for f in lib["folders"])]
    if not matches:
      lib = api.call("libraries", "POST", {"name": "Imported " + mapping["kind"], "folders": [{"fullPath": folder}], "mediaType": "book", "settings": {"storeCoverWithItem": False, "storeMetadataWithItem": False}})
    else:
      lib = matches[0]
    return {"kind": mapping["kind"], "app": "audiobookshelf", "libraryId": lib["id"], "bookPath": str(media / mapping["entityPath"]), "identity": mapping["identity"]}

  def book_item(self, record):
    api = self.api("audiobookshelf")
    for page in range(10000):
      response = api.call(f"libraries/{record['libraryId']}/items", limit=100, page=page)
      for item in response["results"]:
        if item["path"] == record["bookPath"]:
          return api.call(f"items/{item['id']}", expanded=1)
      if (page + 1) * 100 >= response["total"]:
        break
    return None

  def scan(self, record):
    if record["kind"] == "filesystem":
      return
    api = self.api(record["app"])
    if record["app"] != "audiobookshelf" and self.safety(record["app"]) != record["version"]:
      raise ValueError("Application version changed during the operation")
    if record["kind"] == "movie":
      api.command("RescanMovie", movieId=record["id"])
    elif record["kind"] == "tv":
      api.command("RescanSeries", seriesId=record["id"])
    elif record["kind"] == "music":
      api.command("RescanArtist", artistId=record["id"])
    else:
      api.call(f"libraries/{record['libraryId']}/scan", "POST", {})
      deadline = time.monotonic() + 120
      while time.monotonic() < deadline:
        found = self.book_item(record)
        if found:
          identity = record["identity"]
          metadata = {"title": identity["title"], "authors": [{"name": name} for name in identity.get("authors", [identity["author"]])]}
          if identity.get("narrator"):
            metadata["narrators"] = [identity["narrator"]]
          # Explicit approved app metadata only. Never write audio tags.
          api.call(f"items/{found['id']}/media", "PATCH", {"metadata": metadata})
          break
        time.sleep(2)
      else:
        raise ValueError("Audiobookshelf scan did not produce the approved book path")

  def verify(self, record, mapping, destination):
    if record["kind"] == "filesystem":
      return record
    api = self.api(record["app"])
    path = str(destination)
    if record["kind"] == "movie":
      movie = api.call(f"movie/{record['id']}")
      if not movie.get("hasFile") or movie.get("movieFile", {}).get("path") != path:
        raise ValueError("Radarr does not associate the approved file with this movie")
    elif record["kind"] == "tv":
      episodes = api.call("episode", seriesId=record["id"])
      files = {f["id"]: f["path"] for f in api.call("episodefile", seriesId=record["id"])}
      assigned = {e["id"] for e in episodes if files.get(e.get("episodeFileId")) == path}
      if assigned != set(record["episodeIds"]):
        raise ValueError("Sonarr episode assignment differs from the approved mapping")
    elif record["kind"] == "music":
      tracks = api.call("track", albumId=record["albumId"])
      files = {f["id"]: f["path"] for f in api.call("trackfile", artistId=record["id"])}
      assigned = {t["id"] for t in tracks if files.get(t.get("trackFileId")) == path}
      if assigned != {record["trackId"]}:
        raise ValueError("Lidarr track assignment differs from the approved mapping")
    else:
      found = self.book_item(record)
      if not found:
        raise ValueError("Audiobookshelf has not scanned this book; retry verify after scan completion")
      files = found["media"].get("audioFiles", [])
      matching = [f for f in files if f["metadata"]["path"] == path]
      if len(matching) != 1:
        raise ValueError("Audiobookshelf is missing this audio file")
      if matching[0]["index"] != mapping["order"]:
        raise ValueError("Audiobookshelf multipart order differs from approved mapping")
      metadata = found["media"]["metadata"]
      if metadata.get("title") != mapping["identity"]["title"]:
        raise ValueError("Audiobookshelf title differs from approved identity")
      expected = mapping["identity"].get("authors", [mapping["identity"]["author"]])
      if {a["name"] for a in metadata.get("authors", [])} != set(expected):
        raise ValueError("Audiobookshelf author differs from approved identity")
      record["itemId"] = found["id"]
    return record
