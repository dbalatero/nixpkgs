"""Display-only MusicBrainz edition dates; identities still come from Lidarr."""
import json
import time
import urllib.parse
import urllib.request
from uuid import UUID

from .store import packed

_last_request = 0.0


def fetch_dates(album_id):
  global _last_request
  dates = {}
  offset = 0
  while True:
    time.sleep(max(0, 1.1 - (time.monotonic() - _last_request)))
    query = urllib.parse.urlencode({'release-group': album_id, 'limit': 100,
      'offset': offset, 'fmt': 'json'})
    request = urllib.request.Request('https://musicbrainz.org/ws/2/release?' + query,
      headers={'User-Agent': 'media-import/1.0 (personal library importer; netcat.cloud)',
        'Accept': 'application/json'})
    _last_request = time.monotonic()
    with urllib.request.urlopen(request, timeout=15) as response:
      data = json.load(response)
    releases = data['releases']
    dates.update({r['id']: r.get('date') or None for r in releases})
    offset += len(releases)
    if offset >= data['release-count']:
      return dates
    if not releases:
      raise ValueError('Incomplete MusicBrainz release list')


def enrich_dates(store, album_id, releases):
  # Never use the album's original release date for a particular reissue.
  try:
    UUID(album_id)
  except (ValueError, TypeError, AttributeError):
    return releases
  key = 'musicbrainz-release-dates:' + album_id
  cached = store.db.execute('SELECT value, created FROM cache WHERE key=?', (key,)).fetchone()
  dates = json.loads(cached[0]) if cached else {}
  if not cached or time.time() - cached[1] > 30 * 86400:
    try:
      dates = fetch_dates(album_id)
    except (OSError, ValueError, KeyError, TypeError):
      print('Edition dates unavailable from MusicBrainz; continuing with cached dates where available.')
    else:
      with store.db:
        store.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (key, packed(dates), time.time()))
  return [dict(r, editionDate=dates.get(r['foreignReleaseId'])) for r in releases]
