"""Album-sized review; matching evidence stays in SQLite, never audio tags."""
import json
import re
import time
import unicodedata
from pathlib import Path

from .store import packed
from .release_dates import enrich_dates


def disc_folder(source):
  parent = Path(source).parent
  match = re.fullmatch(r'(?:cd|disc|disk)[ _-]*0*([1-9][0-9]*)', parent.name, re.IGNORECASE)
  return int(match[1]) if match else None


def album_folder(source):
  parent = Path(source).parent
  return parent.parent if disc_folder(source) is not None else parent


def options(row):
  data = json.loads(row['mapping'])
  return data.get('options', [data] if data.get('destination') else [])


def track_snapshot(track):
  return {key: track.get(key) for key in ('foreignTrackId', 'foreignRecordingId', 'title', 'duration', 'mediumNumber', 'trackNumber')}


def normalized(text):
  return ''.join(c for c in unicodedata.normalize('NFKD', str(text)).casefold() if c.isalnum())


def track_warnings(mapping, expected):
  evidence = mapping.get('evidence', {})
  tags = evidence.get('guess', {}).get('tags', {})
  warnings = []
  title = tags.get('title')
  if not title:
    warnings.append('no local title tag')
  elif normalized(title) != normalized(expected['title']):
    warnings.append('title differs')
  duration = evidence.get('probe', {}).get('format', {}).get('duration')
  if duration and expected.get('duration'):
    seconds = float(duration)
    delta = abs(seconds - expected['duration'] / 1000)
    if delta > max(3, seconds * 0.02):
      warnings.append(f'duration differs by {delta:.0f}s')
  else:
    warnings.append('duration comparison unavailable')
  return warnings


def choose(items, label, describe, key_choice):
  """Paged single-key choices: IDs are available under details, not the menu."""
  page = 0
  while True:
    subset = items[page * 9:(page + 1) * 9]
    if len(items) > 9:
      print(f'{label}: page {page + 1}/{(len(items) + 8) // 9} — {len(items)} choices; n=next, p=previous')
    for i, item in enumerate(subset, 1):
      print(f'  [{i}] {describe(item)}')
    keys = {str(i): item for i, item in enumerate(subset, 1)}
    default = '1' if len(items) == 1 else None
    answer = key_choice(f'{label}: number; ' + ('Enter=only choice; ' if default else '') + 'n/p=page, v=details, d=defer, i=import saved, q=quit: ', list(keys) + ['n', 'p', 'v', 'd', 'i', 'q'], default)
    if answer in keys:
      return keys[answer]
    if answer in {'d', 'i', 'q'}:
      return answer
    if answer == 'v':
      print(json.dumps(subset, indent=2, ensure_ascii=False))
    elif answer == 'n' and (page + 1) * 9 < len(items):
      page += 1
    elif answer == 'p' and page:
      page -= 1


def release_label(release):
  country = release.get('country') or []
  if isinstance(country, list):
    country = ', '.join(country)
  labels = release.get('label') or []
  if isinstance(labels, list):
    labels = ', '.join(dict.fromkeys(labels))
  return ' | '.join(str(x) for x in (release.get('format') or 'format unknown',
    release.get('editionDate') or 'date unknown', country,
    f"{release.get('trackCount', '?')} tracks", labels, release.get('disambiguation')) if x)


def review_track_matches(group, tracks):
  """Allow a complete, continuously numbered vinyl rip to map to side labels."""
  direct = [[t for t in tracks if t['mediumNumber'] == m['disc']
    and str(t['trackNumber']) == str(m['track'])] for _, m in group]
  if all(len(matches) == 1 for matches in direct):
    return direct, False
  if len(group) != len(tracks) or not tracks or not any(
      not str(t['trackNumber']).isdigit() for t in tracks):
    return direct, False
  local_slots = [(m['disc'], m['track']) for _, m in group]
  # Do not guess missing tracks, partial albums, or non-contiguous local numbering.
  if len({disc for disc, _ in local_slots}) != 1 or sorted(n for _, n in local_slots) != list(range(1, len(tracks) + 1)):
    return direct, False
  slots = [(t['mediumNumber'], t.get('absoluteTrackNumber')) for t in tracks]
  if any(not isinstance(n, int) or n < 1 for _, n in slots) or len(set(slots)) != len(slots):
    return direct, False
  ordered = sorted(tracks, key=lambda t: (t['mediumNumber'], t['absoluteTrackNumber']))
  return [[ordered[m['track'] - 1]] for _, m in group], True


def approved_track_matches(mapping, tracks):
  expected = mapping.get('expectedTrack')
  if expected and expected.get('foreignTrackId'):
    return [t for t in tracks if t.get('foreignTrackId') == expected['foreignTrackId']]
  return [t for t in tracks if t['mediumNumber'] == mapping['disc']
    and str(t['trackNumber']) == str(mapping['track'])]


def associate_album(row, chosen):
  """The user's folder-level album choice overrides per-track search results."""
  data = json.loads(row['mapping'])
  local_options = options(row)
  local = local_options[0] if local_options else data
  evidence = json.loads(packed(data.get('evidence') or local.get('evidence', {})))
  tags = evidence.get('guess', {}).get('tags', {})
  disc = int(str(local.get('disc', tags.get('disc', tags.get('discnumber', 1)))).split('/')[0])
  folder_disc = disc_folder(row['path'])
  explicit_disc = tags.get('disc', tags.get('discnumber'))
  if folder_disc is not None:
    if explicit_disc is not None and int(str(explicit_disc).split('/')[0]) != folder_disc:
      raise ValueError('Disc tag disagrees with disc folder')
    disc = folder_disc
  track = int(str(local.get('track', tags.get('track', tags.get('tracknumber', '')))).split('/')[0])
  if disc < 1 or track < 1:
    raise ValueError('Disc and track numbers must be positive')
  evidence['albumSelection'] = {'basis': 'User selected album for the source folder',
    'foreignAlbumId': chosen['identity']['foreignAlbumId']}
  mapping = {key: json.loads(packed(chosen[key])) for key in
    ('kind', 'identity', 'entityPath', 'appVersion') if key in chosen}
  folder = Path(chosen['destination']).parent
  mapping.update(disc=disc, track=track, evidence=evidence,
    destination=str(folder / f"{disc:02d}-{track:02d} - {Path(row['path']).name}"))
  return mapping


def review_album(store, config, rows, key_choice, apps):
  from .cli import validate_mapping
  folder = album_folder(rows[0]['path'])
  print(f'\nMusic folder: {folder} — {len(rows)} unreviewed tracks')
  print('CD/disc subfolders are reviewed together. Saved, deferred, and imported files are excluded.')
  identities = {}
  for row in rows:
    for option in options(row):
      identity = option.get('identity', {})
      key = (identity.get('foreignArtistId'), identity.get('foreignAlbumId'))
      if all(key):
        identities.setdefault(key, option)
  candidates = list(identities.values())
  if not candidates:
    print('No usable album mappings. Defer for tag/numbering cleanup; source tags will not be edited.')
    answer = key_choice('d=defer folder, q=quit: ', ['d', 'q'])
  else:
    answer = choose(candidates, 'Album', lambda m: f"{m['identity']['artist']} — {m['identity']['title']}", key_choice)
  if isinstance(answer, str):
    return finish_action(store, rows, answer)
  chosen = answer
  identity = chosen['identity']
  group = []
  for row in rows:
    try:
      group.append((row, associate_album(row, chosen)))
    except (TypeError, ValueError) as exc:
      print(f"Cannot read disc/track numbering for {row['path']}: {exc}. No tracks in this folder have been selected.")
      return finish_action(store, rows, key_choice('d=defer entire folder, q=quit: ', ['d', 'q']))
  slots = [(m['disc'], m['track']) for _, m in group]
  if len(set(slots)) != len(slots):
    print('Duplicate disc/track numbers in this source folder; separate copies need manual review.')
    return finish_action(store, rows, key_choice('d=defer folder, q=quit: ', ['d', 'q']))
  # Refresh the selected album read-only so old cached proposals gain full edition labels.
  api = apps.api('lidarr')
  found = api.call('album/lookup', term='lidarr:' + identity['foreignAlbumId'])
  album = next((a for a in found if a['foreignAlbumId'] == identity['foreignAlbumId']), None)
  if not album or not album.get('releases'):
    raise ValueError('Lidarr has no releases for the selected album')
  releases = enrich_dates(store, identity['foreignAlbumId'], album['releases'])
  print(f"\nEdition for {identity['title']} — this review includes {len(group)} tracks")
  print('Track count is a clue, not proof of an edition. Choose the format/edition you own.')
  release = choose(releases, 'Edition', release_label, key_choice)
  if isinstance(release, str):
    return finish_action(store, rows, release)
  for _, mapping in group:
    mapping['identity']['foreignReleaseId'] = release['foreignReleaseId']
    validate_mapping(mapping, config)
  action = key_choice('Load this edition into Lidarr for track review? Monitoring stays off; no files imported. [Enter=yes, d=defer, q=quit]: ', ['y', 'd', 'q'], 'y')
  if action != 'y':
    return finish_action(store, rows, action)
  # Record intent before changing app catalog state, including if metadata loading fails.
  store.event('music-preview-registration', {'identity':group[0][1]['identity'], 'sources':[r['path'] for r, _ in group]})
  store.db.commit()
  store.backup(config['localBackups'])
  from .cli import audit_lock
  # Avoid release-selection changes while a worker is registering an album.
  with audit_lock(store.path.parent / 'music-catalog.lock'):
    record = apps.prepare(group[0][1], Path(config['media']), music_preview=True)
    tracks = api.call('track', albumReleaseId=record['releaseId'])
  group = sorted(group, key=lambda pair: (pair[1]['disc'], pair[1]['track']))
  matched, vinyl_sequence = review_track_matches(group, tracks)
  flagged = vinyl_sequence
  if vinyl_sequence:
    print('REVIEW: Mapping the complete numbered rip to vinyl sides in release order. Confirm the titles and durations below.')
  complete = True
  print('\nLocal track → Lidarr track (disc/track; duration in seconds)')
  for (row, mapping), matches in zip(group, matched):
    if len(matches) != 1 or not matches[0].get('foreignTrackId'):
      print(f"  UNRESOLVED: {row['path']} — no unique track ID at {mapping['disc']}/{mapping['track']}")
      complete = False
      continue
    expected = track_snapshot(matches[0])
    mapping['expectedTrack'] = expected
    if vinyl_sequence:
      mapping['trackMatchBasis'] = 'Complete rip sequence mapped to vinyl release order; user reviewed titles and durations'
    mapping['releaseEvidence'] = release
    issues = track_warnings(mapping, expected)
    mapping['trackWarnings'] = issues
    flagged |= bool(issues)
    evidence = mapping.get('evidence', {})
    local_title = evidence.get('guess', {}).get('tags', {}).get('title') or Path(row['path']).name
    local_duration = evidence.get('probe', {}).get('format', {}).get('duration', '?')
    print(f"  {mapping['disc']:02d}/{mapping['track']:02d}: {local_title} ({local_duration}s) → {expected['mediumNumber']}/{expected['trackNumber']}: {expected['title']} ({(expected.get('duration') or 0) / 1000:g}s)")
    print(f"    {Path(row['path']).name} → {mapping['destination']}")
    if issues:
      print('    REVIEW: ' + '; '.join(issues))
  if len(group) != len(tracks):
    print(f'REVIEW: {len(group)} selected files, {len(tracks)} tracks in this edition; this may be a partial album or separate disc folder.')
    flagged = True
  if not complete:
    return finish_action(store, rows, key_choice('Unresolved track IDs prevent approval. d=defer folder, q=quit: ', ['d', 'q']))
  prompt = 'Save this folder despite the displayed differences? [y=yes, d=defer, q=quit]: ' if flagged else 'Enter=save all displayed tracks, d=defer, q=quit: '
  action = key_choice(prompt, ['y', 'd', 'q'], None if flagged else 'y')
  if action != 'y':
    return finish_action(store, rows, action)
  # Atomic group approval: interruption never leaves half an album selected.
  now = time.time()
  with store.db:
    for row, mapping in group:
      mapping['trackWarningsAccepted'] = flagged
      proposal = store.db.execute('INSERT INTO proposals(revision_id,mapping,created) VALUES (?,?,?)', (row['revision_id'], packed(mapping), now)).lastrowid
      store.db.execute("INSERT INTO decisions(revision_id,proposal_id,action,reason,created) VALUES (?,?,'accept',?,?)", (row['revision_id'], proposal, 'Approved album track comparison' + (' including displayed differences' if flagged else ''), now))
      store.event('decision', {'revision':row['revision_id'], 'proposal':proposal, 'action':'accept', 'reason':'Album track comparison'})
  print(f'Saved {len(group)} tracks. No files imported yet.')
  return 'saved'


def finish_action(store, rows, action):
  if action == 'd':
    for row in rows:
      store.decide(row['revision_id'], 'defer', 'Music folder needs further review', row['id'])
    print('Folder deferred for later cleanup.')
  return action
