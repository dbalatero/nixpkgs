import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from media_import.cli import review, review_rows, pending_proposals, propose
from media_import.music_review import choose, track_snapshot, track_warnings, release_label, review_track_matches
from media_import.release_dates import enrich_dates
from media_import.store import Store
from media_import.apps import Apps


class MusicReviewTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.base = Path(self.temp.name)
    self.source = self.base / 'source'
    self.source.mkdir()
    self.store = Store(self.base / 'audit.sqlite', self.source)
    self.config = {'media': str(self.base / 'media'), 'localBackups': str(self.base / 'backups')}
    self.release = {'id': 4, 'foreignReleaseId': 'release', 'format': 'Vinyl', 'trackCount': 2, 'country': ['US']}
    self.tracks = [{'id': n, 'mediumNumber': 1, 'trackNumber': str(n), 'foreignTrackId': f'track-{n}', 'foreignRecordingId': f'recording-{n}', 'title': f'Song {n}', 'duration': 60000} for n in (1, 2)]
    self.apps = Mock()
    self.apps.prepare.return_value = {'albumId': 3, 'releaseId': 4}
    self.apps.api.return_value.call.side_effect = lambda endpoint, **kw: [{'foreignAlbumId': 'album', 'releases': [self.release]}] if endpoint == 'album/lookup' else self.tracks
    self.output = io.StringIO()
    self.redirect = contextlib.redirect_stdout(self.output)
    self.redirect.__enter__()

  def tearDown(self):
    self.redirect.__exit__(None, None, None)
    self.store.db.close()
    self.temp.cleanup()

  def setup_album(self, folder='Music/Album', prepare=True):
    for n in (1, 2):
      path = self.source / folder / f'{n}.flac'
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_bytes(b'untouched')
    self.store.inventory(now=0)
    self.store.inventory(now=601)
    for row in self.store.candidates():
      if Path(row['path']).parent != Path(folder) or not prepare:
        continue
      n = int(Path(row['path']).stem)
      mapping = {'kind': 'music', 'identity': {'artist': 'Artist', 'title': 'Album', 'foreignArtistId': 'artist', 'foreignAlbumId': 'album', 'foreignReleaseId': 'release'}, 'entityPath': 'music/Artist', 'destination': f'music/Artist/Album/{n}.flac', 'disc': 1, 'track': n, 'evidence': {'guess': {'tags': {'title': f'Song {n}'}}, 'probe': {'format': {'duration': '60'}}}}
      self.store.propose(row['revision_id'], {'options': [mapping]})

  def test_folder_expands_limit_but_respects_file_filter_and_source_folder(self):
    self.setup_album()
    self.setup_album('Music/Other Copy')
    rows = review_rows(self.store, limit=1)
    self.assertEqual(len(rows), 2)
    self.assertTrue(all(Path(r['path']).parent == Path('Music/Album') for r in rows))
    self.assertEqual(len(review_rows(self.store, ids=[rows[0]['file_id']], limit=1)), 1)

  def test_album_approval_records_track_ids_without_import_or_file_writes(self):
    self.setup_album()
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1', '1', 'y', 'y']):
      self.assertTrue(review(self.store, self.config, limit=1))
    self.assertEqual(len(pending_proposals(self.store)), 2)
    self.assertEqual(self.store.db.execute('SELECT count(*) FROM operations').fetchone()[0], 0)
    self.assertFalse((self.base / 'media').exists())
    for path in self.source.rglob('*.flac'):
      self.assertEqual(path.read_bytes(), b'untouched')
    mappings = [json.loads(r[0]) for r in self.store.db.execute('SELECT mapping FROM proposals WHERE id IN (SELECT proposal_id FROM decisions)')]
    self.assertEqual({m['expectedTrack']['foreignTrackId'] for m in mappings}, {'track-1', 'track-2'})
    self.assertEqual(review_rows(self.store), [])
    self.assertNotIn('foreignAlbumId', self.output.getvalue())

  def test_selected_album_includes_track_with_different_search_results(self):
    self.setup_album()
    row = review_rows(self.store)[1]
    data = json.loads(row['mapping'])
    data['options'][0]['identity']['foreignAlbumId'] = 'wrong-search-result'
    data['options'][0]['identity']['title'] = 'Unrelated album'
    self.store.propose(row['revision_id'], data)
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1', '1', 'y', 'y']):
      self.assertTrue(review(self.store, self.config))
    saved = [json.loads(r[0]) for r in self.store.db.execute('SELECT mapping FROM proposals WHERE id IN (SELECT proposal_id FROM decisions)')]
    self.assertEqual(len(saved), 2)
    self.assertEqual({m['identity']['foreignAlbumId'] for m in saved}, {'album'})
    second = next(m for m in saved if m['track'] == 2)
    self.assertEqual(second['evidence']['guess']['tags']['title'], 'Song 2')
    self.assertEqual(second['expectedTrack']['foreignTrackId'], 'track-2')
    self.assertEqual(second['destination'], 'music/Artist/Album/01-02 - 2.flac')

  def test_selected_album_includes_track_with_no_search_options(self):
    self.setup_album()
    row = review_rows(self.store)[1]
    evidence = {'guess': {'tags': {'title': 'Song 2', 'track': '2/2'}}, 'probe': {'format': {'duration': '60'}}}
    self.store.propose(row['revision_id'], {'options': [], 'evidence': evidence})
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1', '1', 'y', 'y']):
      self.assertTrue(review(self.store, self.config))
    self.assertEqual(len(pending_proposals(self.store)), 2)

  def test_missing_number_leaves_entire_folder_unapproved(self):
    self.setup_album()
    row = review_rows(self.store)[1]
    self.store.propose(row['revision_id'], {'options': [], 'evidence': {'guess': {'tags': {'title': 'Song 2'}}}})
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1', 'q']):
      self.assertFalse(review(self.store, self.config))
    self.assertEqual(pending_proposals(self.store), [])
    self.apps.prepare.assert_not_called()

  def test_quit_before_registration_has_no_app_mutations_or_decisions(self):
    self.setup_album()
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1', '1', 'q']):
      self.assertFalse(review(self.store, self.config))
    self.apps.prepare.assert_not_called()
    self.assertEqual(pending_proposals(self.store), [])

  def test_track_mismatch_has_no_enter_default_and_defer_saves_no_approval(self):
    self.setup_album()
    self.tracks[1]['title'] = 'Wrong song'
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1', '1', 'y', 'd']) as menu:
      review(self.store, self.config)
    self.assertIsNone(menu.call_args.args[2])
    self.assertIn('title differs', self.output.getvalue())
    self.assertEqual(pending_proposals(self.store), [])
    self.assertEqual(self.store.db.execute("SELECT count(*) FROM decisions WHERE action='defer'").fetchone()[0], 2)

  def test_missing_track_id_cannot_be_approved(self):
    self.setup_album()
    self.tracks[1]['foreignTrackId'] = None
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1', '1', 'y', 'q']) as menu:
      self.assertFalse(review(self.store, self.config))
    self.assertEqual(menu.call_args.args[1], ['d', 'q'])
    self.assertEqual(pending_proposals(self.store), [])

  def test_parallel_preparation_shares_lookup_and_saves_progress(self):
    import threading
    self.setup_album(prepare=False)
    barrier = threading.Barrier(2)
    def inspect(*args):
      barrier.wait(timeout=5)
      return {}
    with patch('media_import.cli.inspect_file', side_effect=inspect), patch('media_import.cli.guess', return_value={'tags': {'artist':'Artist','album':'Album'}}), patch('media_import.cli.Apps') as apps:
      apps.return_value.lookup.return_value = {'results':[], 'version':'test'}
      propose(self.store, {**self.config, 'prepWorkers':2}, 2, ['music'])
      apps.return_value.lookup.assert_called_once()
    self.assertEqual(len(review_rows(self.store)), 2)
    self.assertIn('2/2 (100%)', self.output.getvalue())
    self.assertEqual(self.store.db.execute('SELECT count(*) FROM cache').fetchone()[0], 1)

  def test_parallel_lookup_failure_preserves_each_file_as_reviewable(self):
    self.setup_album(prepare=False)
    with patch('media_import.cli.inspect_file', return_value={}), patch('media_import.cli.guess', return_value={'tags': {'artist':'Artist','album':'Album'}}), patch('media_import.cli.Apps') as apps:
      apps.return_value.lookup.side_effect = ValueError('Metadata temporarily unavailable')
      propose(self.store, {**self.config, 'prepWorkers':2}, 2, ['music'])
      apps.return_value.lookup.assert_called_once()
    rows = review_rows(self.store)
    self.assertEqual(len(rows), 2)
    self.assertTrue(all('Metadata temporarily unavailable' in json.loads(r['mapping'])['issue'] for r in rows))

  def test_propose_limit_finishes_only_selected_folder(self):
    self.setup_album(prepare=False)
    self.setup_album('Music/Other', prepare=False)
    with patch('media_import.cli.inspect_file', return_value={}), patch('media_import.cli.guess', return_value={'tags': {'artist': 'Artist', 'album': 'Album'}}), patch('media_import.cli.Apps') as apps:
      apps.return_value.lookup.return_value = {'results': [], 'version': 'test'}
      propose(self.store, self.config, 1, ['music'])
    rows = review_rows(self.store)
    self.assertEqual(len(rows), 2)
    self.assertTrue(all(Path(r['path']).parent == Path('Music/Album') for r in rows))

  def test_paged_release_selection_keeps_ids_stable(self):
    menu = Mock(side_effect=['n', '2'])
    self.assertEqual(choose(list(range(12)), 'Edition', str, menu), 10)

  def test_verify_rejects_track_identity_drift(self):
    api = Mock()
    api.call.side_effect = lambda endpoint, **kw: self.tracks if endpoint == 'track' else [{'id': 8, 'path': '/library/song.flac'}]
    self.tracks[0]['trackFileId'] = 8
    expected = track_snapshot(self.tracks[0])
    self.tracks[0]['foreignTrackId'] = 'different-id'
    apps = Apps({})
    with patch.object(apps, 'api', return_value=api):
      with self.assertRaisesRegex(ValueError, 'identity differs'):
        apps.verify({'kind': 'music', 'app': 'lidarr', 'albumId': 3, 'id': 2, 'trackId': 1}, {'expectedTrack': expected}, Path('/library/song.flac'))

  def test_music_scan_uses_explicit_approved_track_without_replacement(self):
    api = Mock()
    track = self.tracks[0]
    def call(endpoint, **kw):
      return {'artist/7': {'path': '/media/music/Artist'}, 'track': [track], 'trackfile': [],
        'manualimport': [{'path': '/media/music/Artist/Album/song.flac', 'quality': {'quality': {'id': 6}}}]}[endpoint]
    api.call.side_effect = call
    apps = Apps({})
    with patch.object(apps, 'api', return_value=api), patch.object(apps, 'safety', return_value='test'):
      apps.scan({'kind': 'music', 'app': 'lidarr', 'id': 7, 'version': 'test', 'albumId': 3,
        'releaseId': 4, 'trackId': track['id'], 'expectedTrack': track_snapshot(track),
        'expectedPath': '/media/music/Artist/Album/song.flac'})
    name = api.command.call_args.args[0]
    payload = api.command.call_args.kwargs
    self.assertEqual(name, 'ManualImport')
    self.assertFalse(payload['replaceExistingFiles'])
    self.assertEqual(payload['files'][0]['trackIds'], [track['id']])
    self.assertTrue(payload['files'][0]['disableReleaseSwitching'])

  def test_music_scan_refuses_missing_scope(self):
    api = Mock()
    apps = Apps({})
    with patch.object(apps, 'api', return_value=api), patch.object(apps, 'safety', return_value='test'):
      with self.assertRaisesRegex(ValueError, 'approved destination'):
        apps.scan({'kind': 'music', 'app': 'lidarr', 'id': 7, 'version': 'test'})
    api.command.assert_not_called()

  def test_disc_folders_share_review_limit_and_keep_separate_track_numbers(self):
    from media_import.music_review import associate_album, options
    self.setup_album('Music/Double/CD1')
    self.setup_album('Music/Double/CD2')
    self.setup_album('Music/Other/CD1')
    rows = review_rows(self.store, limit=1)
    self.assertEqual(len(rows), 4)
    chosen = options(rows[0])[0]
    mapped = [associate_album(row, chosen) for row in rows]
    self.assertEqual({(m['disc'],m['track']) for m in mapped}, {(1,1),(1,2),(2,1),(2,2)})
    self.assertEqual(len({m['destination'] for m in mapped}), 4)

  def test_disc_folder_conflicting_with_tag_is_not_silently_assigned(self):
    from media_import.music_review import associate_album, options
    self.setup_album('Music/Double/CD2')
    row = review_rows(self.store)[0]
    data = json.loads(row['mapping'])
    data['options'][0]['evidence']['guess']['tags']['disc'] = '1'
    row['mapping'] = json.dumps(data)
    with self.assertRaisesRegex(ValueError, 'disagrees'):
      associate_album(row, options(row)[0])

  def test_music_metadata_profile_includes_live_and_bootleg_without_editing_standard(self):
    api = Mock()
    profile = {'id':1, 'name':'Standard', 'primaryAlbumTypes':[{'allowed':True}],
      'secondaryAlbumTypes':[{'allowed':False}], 'releaseStatuses':[{'allowed':False}]}
    api.call.side_effect = [[profile], {'id':3}]
    apps = Apps({'musicMetadataProfile':'Existing library import'})
    with patch.object(apps, 'api', return_value=api):
      self.assertEqual(apps.music_metadata_profile(),3)
      self.assertEqual(apps.music_metadata_profile(),3)
    payload = api.call.call_args.args[2]
    self.assertEqual(payload['name'],'Existing library import')
    self.assertTrue(payload['secondaryAlbumTypes'][0]['allowed'])
    self.assertTrue(payload['releaseStatuses'][0]['allowed'])
    self.assertFalse(profile['secondaryAlbumTypes'][0]['allowed'])
    self.assertEqual(api.call.call_count,2)

  def test_release_loading_refreshes_album_without_substituting_cd_edition(self):
    identity = {'foreignAlbumId':'album', 'foreignReleaseId':'digital'}
    cd = {'id':9, 'foreignReleaseId':'cd', 'trackCount':11}
    digital = {'id':10, 'foreignReleaseId':'digital', 'trackCount':2}
    api = Mock()
    api.call.side_effect = [
      [{'id':3, 'foreignAlbumId':'album', 'releases':[cd]}],
      [{'id':3, 'foreignAlbumId':'album', 'releases':[cd,digital]}], self.tracks]
    album, release = Apps({}).ready_music_release(api,7,identity)
    self.assertEqual(release['foreignReleaseId'],'digital')
    api.command.assert_called_once_with('RefreshAlbum',albumId=3)

  def test_loaded_release_does_not_trigger_another_refresh(self):
    release = {'id':10,'foreignReleaseId':'digital','trackCount':2}
    api = Mock()
    api.call.side_effect = [[{'id':3,'foreignAlbumId':'album','releases':[release]}],self.tracks]
    Apps({}).ready_music_release(api,7,{'foreignAlbumId':'album','foreignReleaseId':'digital'})
    api.command.assert_not_called()

  def test_release_loading_waits_for_complete_track_list(self):
    release = {'id':10,'foreignReleaseId':'digital','trackCount':2}
    album = {'id':3,'foreignAlbumId':'album','releases':[release]}
    api = Mock()
    api.call.side_effect = [[album],self.tracks[:1],[album],self.tracks]
    Apps({}).ready_music_release(api,7,{'foreignAlbumId':'album','foreignReleaseId':'digital'})
    api.command.assert_called_once()

  def test_unavailable_release_times_out_without_selecting_another(self):
    api = Mock()
    api.call.return_value = [{'id':3,'foreignAlbumId':'album','releases':[]}]
    with patch('media_import.apps.time.monotonic',side_effect=[0,121]):
      with self.assertRaisesRegex(ValueError,'No substitute edition'):
        Apps({}).ready_music_release(api,7,{'foreignAlbumId':'album','foreignReleaseId':'missing'})
    api.command.assert_called_once_with('RefreshAlbum',albumId=3)

  def test_complete_vinyl_rip_maps_across_records_in_release_order(self):
    group = [(None, {'disc':1, 'track':n}) for n in range(1,5)]
    tracks = [dict(self.tracks[0], mediumNumber=n // 2 + 1,
      absoluteTrackNumber=n % 2 + 1, trackNumber=side, foreignTrackId=side)
      for n, side in enumerate('ABCD')]
    matches, sequence = review_track_matches(group, list(reversed(tracks)))
    self.assertTrue(sequence)
    self.assertEqual([m[0]['foreignTrackId'] for m in matches], list('ABCD'))
    self.assertFalse(review_track_matches(group[:3], tracks)[1])
    tracks[1]['absoluteTrackNumber'] = 1
    self.assertFalse(review_track_matches(group, tracks)[1])

  def test_apply_uses_approved_vinyl_track_id_and_checks_metadata(self):
    track = dict(self.tracks[0], mediumNumber=2, trackNumber='C')
    mapping = {'kind':'music', 'identity':{'foreignArtistId':'artist',
      'foreignAlbumId':'album', 'foreignReleaseId':'release'},
      'disc':1, 'track':3, 'expectedTrack':track_snapshot(track)}
    apps = Apps({})
    key = ('artist','album','release',None,None)
    apps.music_albums[key] = ({'id':7}, [track], {})
    self.assertEqual(apps.prepare(mapping, self.base)['trackId'], track['id'])
    track['title'] = 'Unexpected changed title'
    with self.assertRaisesRegex(ValueError, 'metadata changed'):
      apps.prepare(mapping, self.base)

  def test_vinyl_sequence_requires_explicit_confirmation_and_saves_ids(self):
    self.setup_album()
    for n, track in enumerate(self.tracks):
      track.update(trackNumber='AB'[n], absoluteTrackNumber=n+1)
    with patch('media_import.cli.Apps', return_value=self.apps), patch('media_import.cli.key_choice', side_effect=['1','1','y','y']):
      review(self.store, self.config)
    approved = pending_proposals(self.store)
    self.assertEqual(len(approved), 2)
    self.assertIn('Mapping the complete numbered rip', self.output.getvalue())
    mappings = [json.loads(self.store.db.execute('SELECT mapping FROM proposals WHERE id=?', (pid,)).fetchone()[0]) for pid in approved]
    self.assertEqual([m['expectedTrack']['trackNumber'] for m in mappings], ['A','B'])
    self.assertTrue(all(m['trackWarningsAccepted'] for m in mappings))

  def test_edition_dates_join_exact_release_ids_and_use_cache(self):
    album = '77cf47ba-58cd-3f3d-a5f9-79bf89860421'
    releases = [dict(self.release), dict(self.release, foreignReleaseId='other')]
    with patch('media_import.release_dates.fetch_dates', return_value={'release':'2010'}) as fetch:
      enriched = enrich_dates(self.store, album, releases)
      self.assertEqual(enriched[0]['editionDate'], '2010')
      self.assertIsNone(enriched[1]['editionDate'])
      self.assertEqual(enrich_dates(self.store, album, releases), enriched)
      fetch.assert_called_once()
    self.assertNotIn('editionDate', releases[0])

  def test_edition_date_failure_keeps_menu_usable_without_album_year(self):
    with patch('media_import.release_dates.fetch_dates', side_effect=OSError('offline')):
      enriched = enrich_dates(self.store, '77cf47ba-58cd-3f3d-a5f9-79bf89860421',
        [dict(self.release, releaseDate='1965-01-01')])
    self.assertIn('date unknown', release_label(enriched[0]))
    self.assertNotIn('1965', release_label(enriched[0]))

  def test_edition_label_shows_date_and_record_label(self):
    label = release_label(dict(self.release, editionDate='2010', label=['Analogue Productions']))
    self.assertIn('2010', label)
    self.assertIn('Analogue Productions', label)

  def test_title_punctuation_normalized_but_duration_mismatch_flagged(self):
    mapping = {'evidence': {'guess': {'tags': {'title': 'Café — Song'}}, 'probe': {'format': {'duration': '60'}}}}
    self.assertEqual(track_warnings(mapping, {'title': 'Cafe Song', 'duration': 60000}), [])
    self.assertTrue(track_warnings(mapping, {'title': 'Cafe Song', 'duration': 90000}))


if __name__ == '__main__':
  unittest.main()
