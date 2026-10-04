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
    try:
      result = self.call("command", "POST", {"name": name, **arguments})
    except ValueError as exc:
      raise ValueError(f"App command {name}: {exc}") from None
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
      status = self.call(f"command/{result['id']}")
      if status["status"].lower() == "completed":
        return status
      if status["status"].lower() in {"failed", "aborted", "cancelled"}:
        raise ValueError(f"App command {name} failed; inspect the application log")
      time.sleep(0.25)
    raise ValueError(f"App command {name} still running; reconcile before retrying")


class Apps:
  def __init__(self, config):
    self.config = config
    self.refreshed_artists = set()
    self.music_albums = {}
    self.music_profile_id = None

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
    # Only the explicitly declared local client may coexist with migration.
    # Source-removal remains forbidden; unrelated integrations still fail closed.
    allowed = self.config.get("torrentClients", {}).get(name)
    for client in api.call("downloadclient"):
      fields = {field["name"]: field.get("value", "") for field in client["fields"]}
      if (not allowed or client["name"] != allowed["name"]
          or client["implementation"] != "QBittorrent"
          or client.get("removeCompletedDownloads", True)
          or client.get("removeFailedDownloads", True)
          or any(fields.get(key, "") != value for key, value in allowed["fields"].items())):
        raise ValueError(f"{name} has an undeclared or unsafe download client")
    for endpoint in ("indexer", "importlist"):
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
    self.music_metadata_profile()
    self.configure_music_root()
    self.bootstrap_books()

  def music_metadata_profile(self):
    name = self.config.get('musicMetadataProfile')
    if not name:
      return None
    if self.music_profile_id is not None:
      return self.music_profile_id
    api = self.api('lidarr')
    profiles = api.call('metadataprofile')
    profile = next((p for p in profiles if p['name'] == name), None)
    desired = json.loads(json.dumps(profile or profiles[0]))
    desired['name'] = name
    for group in ('primaryAlbumTypes', 'secondaryAlbumTypes', 'releaseStatuses'):
      for entry in desired[group]:
        entry['allowed'] = True
    if profile is None:
      desired.pop('id', None)
      profile = api.call('metadataprofile', 'POST', desired)
    elif desired != profile:
      api.call(f"metadataprofile/{profile['id']}", 'PUT', desired)
    self.music_profile_id = profile['id']
    return self.music_profile_id

  def configure_music_root(self):
    root = self.config.get('musicRoot')
    if not root:
      return
    api = self.api('lidarr')
    if any(r['path'] == root for r in api.call('rootfolder')):
      return
    api.call('rootfolder', 'POST', {
      'name': 'Imported music', 'path': root,
      'defaultMetadataProfileId': self.music_metadata_profile() or api.call('metadataprofile')[0]['id'],
      'defaultQualityProfileId': api.call('qualityprofile')[0]['id'],
      'defaultMonitorOption': 'none', 'defaultNewItemMonitorOption': 'none', 'defaultTags': []})

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

  def ready_music_release(self, api, artist_id, identity):
    """Artist refresh may finish before newly added albums have their tracks."""
    deadline = time.monotonic() + 120
    refreshed = False
    announced = False
    while True:
      albums = [a for a in api.call('album', artistId=artist_id)
        if a['foreignAlbumId'] == identity['foreignAlbumId']]
      if len(albums) > 1:
        raise ValueError('Approved album is not unique in Lidarr')
      if albums:
        album = albums[0]
        releases = [r for r in album['releases'] if r['foreignReleaseId'] == identity['foreignReleaseId']]
        if len(releases) > 1:
          raise ValueError('Approved release is not unique in Lidarr')
        if releases:
          release = releases[0]
          tracks = api.call('track', albumReleaseId=release['id'])
          if tracks and len(tracks) == release.get('trackCount') and all(t.get('foreignTrackId') for t in tracks):
            return album, release
        if not refreshed:
          print('Loading the selected album edition and its track list from Lidarr…', flush=True)
          announced = True
          api.command('RefreshAlbum', albumId=album['id'])
          refreshed = True
          continue
      if time.monotonic() >= deadline:
        raise ValueError('Lidarr has not finished loading the selected release and tracks. No substitute edition was selected; retry this review.')
      if not announced:
        print('Waiting for Lidarr to load the selected album…', flush=True)
        announced = True
      time.sleep(0.5)

  def prepare(self, mapping, media, music_preview=False):
    """Register only the approved identity, unmonitored, before creating any links."""
    kind = mapping["kind"]
    identity = mapping["identity"]
    music_key = tuple(identity.get(k) for k in ('foreignArtistId', 'foreignAlbumId', 'foreignReleaseId')) + (mapping.get('entityPath'), mapping.get('appVersion'))
    if kind == 'music' and not music_preview and not mapping.get('alternate'):
      if music_key not in self.music_albums:
        base = self.prepare(mapping, media, music_preview=True)
        api = self.api('lidarr')
        self.music_albums[music_key] = (base, api.call('track', albumReleaseId=base['releaseId']),
          {f['id']:f['path'] for f in api.call('trackfile', artistId=base['id'])})
      base, tracks, files = self.music_albums[music_key]
      from .music_review import track_snapshot, approved_track_matches
      matches = approved_track_matches(mapping, tracks)
      if len(matches) != 1:
        raise ValueError('Approved disc/track is not uniquely represented in Lidarr')
      track = matches[0]
      if mapping.get('expectedTrack') and track_snapshot(track) != mapping['expectedTrack']:
        raise ValueError('Lidarr track metadata changed since review; re-review before importing')
      return {**base, 'trackId':track['id'], 'expectedTrack':track_snapshot(track),
        'existingPaths':[files.get(track['trackFileId'], 'UNKNOWN EXISTING FILE')] if track.get('hasFile') else []}
    if mapping.get("alternate") or kind == "companion":
      return {"kind": "filesystem"}
    if kind in {"audiobook", "spoken-word", "podcast"}:
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
        entity["metadataProfileId"] = self.music_metadata_profile() or metadata_profiles[0]["id"]
      entity = api.call(resource, "POST", entity)
    if kind == 'music':
      profile = self.music_metadata_profile()
      if profile is not None and entity['metadataProfileId'] != profile:
        entity['metadataProfileId'] = profile
        api.call(f"artist/{entity['id']}", 'PUT', entity)
        self.refreshed_artists.discard(entity['id'])
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
      # Initial automatic refresh can overlap our explicit refresh on a new series.
      # Reconcile duplicate rows before saving immutable episode assignments.
      if len(selected) > len(wanted):
        api.command("RefreshSeries", seriesId=entity_id)
        episodes = api.call("episode", seriesId=entity_id)
        selected = [e for e in episodes if e["seasonNumber"] == mapping["season"] and e["episodeNumber"] in wanted]
      if {e["episodeNumber"] for e in selected} != wanted:
        raise ValueError("Approved episode numbers do not exist in Sonarr metadata")
      if len(selected) != len(wanted):
        raise ValueError("Sonarr has duplicate records for the approved episodes; refresh series metadata before retrying")
      record["episodeIds"] = [e["id"] for e in selected]
      existing = {f["id"]: f["path"] for f in api.call("episodefile", seriesId=entity_id)}
      record["existingPaths"] = [existing.get(e["episodeFileId"], "UNKNOWN EXISTING FILE") for e in selected if e.get("hasFile")]
    else:
      if entity_id not in self.refreshed_artists:
        api.command("RefreshArtist", artistId=entity_id)
        self.refreshed_artists.add(entity_id)
      album, release = self.ready_music_release(api, entity_id, identity)
      selected = [release]
      # Never switch a release for an already imported album.
      existing_tracks = api.call("track", albumId=album["id"])
      if any(t.get("hasFile") for t in existing_tracks) and not selected[0].get("monitored"):
        raise ValueError("Album already has files from a different release")
      album["monitored"] = False
      album["anyReleaseOk"] = False
      for release in album["releases"]:
        release["monitored"] = release["foreignReleaseId"] == identity["foreignReleaseId"]
      api.call(f"album/{album['id']}", "PUT", album)
      record.update(albumId=album['id'], releaseId=selected[0]['id'])
      if music_preview:
        return record
      tracks = api.call("track", albumReleaseId=selected[0]['id'])
      from .music_review import approved_track_matches
      matches = approved_track_matches(mapping, tracks)
      if len(matches) != 1:
        raise ValueError("Approved disc/track is not uniquely represented in Lidarr")
      from .music_review import track_snapshot
      expected = mapping.get('expectedTrack')
      if expected and track_snapshot(matches[0]) != expected:
        raise ValueError('Lidarr track metadata changed since review; re-review before importing')
      record['expectedTrack'] = track_snapshot(matches[0])
      existing = {f["id"]: f["path"] for f in api.call("trackfile", artistId=entity_id)}
      record.update(albumId=album["id"], trackId=matches[0]["id"], existingPaths=[existing.get(matches[0]["trackFileId"], "UNKNOWN EXISTING FILE")] if matches[0].get("hasFile") else [])
    return record

  def prepare_books(self, mapping, media):
    api = self.api("audiobookshelf")
    folder = str(media / ({"spoken-word": "spoken-word", "podcast": "podcasts"}.get(mapping["kind"], "audiobooks")))
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
      self.scan_music([record])
    else:
      api.call(f"libraries/{record['libraryId']}/scan", "POST", {})
      deadline = time.monotonic() + 120
      while time.monotonic() < deadline:
        found = self.book_item(record)
        if found and any(f.get("metadata", {}).get("path") == record["expectedPath"]
          for f in found["media"].get("audioFiles", [])):
          identity = record["identity"]
          metadata = {"title": identity["title"], "authors": [{"name": name} for name in identity.get("authors", [identity["author"]])]}
          if identity.get("series"):
            metadata["series"] = identity["series"]
          if identity.get("narrator"):
            metadata["narrators"] = [identity["narrator"]]
          # Explicit approved app metadata only. Never write audio tags.
          api.call(f"items/{found['id']}/media", "PATCH", {"metadata": metadata})
          break
        time.sleep(2)
      else:
        raise ValueError("Audiobookshelf scan did not register the expected audio file within 120 seconds")

  def scan_music(self, records):
    """One explicit import command per album, after every copy is published."""
    api = self.api('lidarr')
    first = records[0]
    if self.safety('lidarr') != first['version']:
      raise ValueError('Application version changed during the operation')
    if any(not r.get('expectedPath') for r in records):
      raise ValueError('Music scan requires the approved destination path')
    if any((r['id'],r['albumId'],r['releaseId'],r['version']) != (first['id'],first['albumId'],first['releaseId'],first['version']) for r in records):
      raise ValueError('Music import group mixes albums or releases')
    artist = api.call(f"artist/{first['id']}")
    tracks = {t['id']:t for t in api.call('track', albumReleaseId=first['releaseId'])}
    files = {f['id']:f['path'] for f in api.call('trackfile', artistId=first['id'])}
    from .music_review import track_snapshot
    previews, payload = {}, []
    for record in records:
      path = record['expectedPath']
      if not Path(path).is_relative_to(Path(artist['path'])):
        raise ValueError('Music import path must be inside the registered artist library')
      track = tracks.get(record['trackId'])
      if track is None or track_snapshot(track) != record['expectedTrack']:
        raise ValueError('Music track metadata changed before file registration')
      existing = files.get(track.get('trackFileId'))
      if existing:
        if existing != path:
          raise ValueError('Approved track already has another file; replacement is prohibited')
        continue
      folder = str(Path(path).parent)
      if folder not in previews:
        previews[folder] = api.call('manualimport', folder=folder, artistId=record['id'],
          filterExistingFiles='false', replaceExistingFiles='false')
      exact = [f for f in previews[folder] if f['path'] == path and f.get('quality')]
      if len(exact) != 1:
        raise ValueError('Lidarr cannot read the approved music file')
      payload.append({'path':path, 'artistId':record['id'], 'albumId':record['albumId'],
        'albumReleaseId':record['releaseId'], 'trackIds':[record['trackId']],
        'quality':exact[0]['quality'], 'disableReleaseSwitching':True})
    if payload:
      api.command('ManualImport', importMode='copy', replaceExistingFiles=False, files=payload)

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
      for attempt in range(2):
        episodes = api.call("episode", seriesId=record["id"])
        wanted = set(mapping['episodes'])
        selected = [e for e in episodes if e['seasonNumber'] == mapping['season'] and e['episodeNumber'] in wanted]
        unique = len(selected) == len(wanted) and {e['episodeNumber'] for e in selected} == wanted
        files = {f["id"]: f["path"] for f in api.call("episodefile", seriesId=record["id"])}
        assigned = {e["id"] for e in episodes if files.get(e.get("episodeFileId")) == path}
        expected = {e['id'] for e in selected}
        if unique and assigned == expected:
          record['episodeIds'] = sorted(expected)
          break
        if attempt == 0 and (not unique or expected != set(record['episodeIds'])):
          # Automatic initial refresh may complete after prepare(), creating duplicate
          # rows. Reconcile metadata and rescan, preserving approved episode numbers.
          api.command('RefreshSeries', seriesId=record['id'])
          api.command('RescanSeries', seriesId=record['id'])
          continue
        raise ValueError("Sonarr episode assignment differs from the approved mapping")
    elif record["kind"] == "music":
      tracks = api.call("track", albumId=record["albumId"])
      files = {f["id"]: f["path"] for f in api.call("trackfile", artistId=record["id"])}
      assigned = {t["id"] for t in tracks if files.get(t.get("trackFileId")) == path}
      if assigned != {record["trackId"]}:
        raise ValueError("Lidarr track assignment differs from the approved mapping")
      from .music_review import track_snapshot
      expected = mapping.get('expectedTrack') or record.get('expectedTrack')
      actual = next(t for t in tracks if t['id'] == record['trackId'])
      if expected and track_snapshot(actual) != expected:
        raise ValueError('Lidarr track identity differs from the reviewed metadata')
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
      for series in mapping["identity"].get("series", []):
        if not any(s["name"] == series["name"] and str(s.get("sequence")) == str(series["sequence"])
          for s in metadata.get("series", [])):
          raise ValueError("Audiobookshelf series/episode number differs from approved mapping")
      record["itemId"] = found["id"]
    return record
