import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import ebook_import as e


class EbookImportTest(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.settings = {name: str(self.root / name) for name in ('state', 'work', 'incoming', 'outbox', 'source')}
    for value in self.settings.values():
      Path(value).mkdir()
    self.settings['sevenzip'] = os.environ.get('SEVENZIP', '7zz')
    self.db = e.connect(Path(self.settings['state']))
    self.addCleanup(self.db.close)

  def test_formats_per_book(self):
    paths = list(map(Path, ['a.epub', 'a.mobi', 'a.pdf', 'b.azw3', 'b.mobi', 'c.pdf']))
    selected, review, alternatives, _ = e.choose(paths)
    self.assertEqual(selected, list(map(Path, ['a.epub', 'b.azw3', 'c.pdf'])))
    self.assertEqual((review, alternatives), ([], 3))

  def test_ambiguity_and_legacy(self):
    selected, review, _, _ = e.choose(list(map(Path, ['Decagon House Murders - Unknown.epub', 'Yukito - Decagon House Murders.azw3', 'old.lit'])))
    self.assertEqual(selected, [])
    self.assertEqual(len(review), 3)

  def test_source_paths(self):
    for name in ('../book.epub', '/book.epub', 'C:/book.epub'):
      with self.assertRaises(ValueError):
        e.safe_relative(name)
    (self.root / 'link.epub').symlink_to('/etc/passwd')
    with self.assertRaises(ValueError):
      e.checked_source(self.root, 'link.epub')

  def test_nested_archive(self):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, 'w') as archive:
      archive.writestr('book.epub', b'epub')
      archive.writestr('book.mobi', b'mobi')
    with zipfile.ZipFile(self.root / 'outer.zip', 'w') as archive:
      archive.writestr('inner.zip', inner.getvalue())
    e.unpack(self.root, self.settings['sevenzip'])
    self.assertEqual((self.root / 'book.epub').read_bytes(), b'epub')

  def test_archive_traversal(self):
    with zipfile.ZipFile(self.root / 'bad.zip', 'w') as archive:
      archive.writestr('../escape.epub', b'bad')
    with self.assertRaises(ValueError):
      e.unpack(self.root, self.settings['sevenzip'])

  def test_archive_duplicate_member_only_accepts_identical_bytes(self):
    (self.root / 'book.epub').write_bytes(b'same')
    with zipfile.ZipFile(self.root / 'pack.zip', 'w') as archive:
      archive.writestr('book.epub', b'same')
    e.unpack(self.root, self.settings['sevenzip'])
    (self.root / 'book.epub').write_bytes(b'different')
    with self.assertRaisesRegex(ValueError, 'collision'):
      e.unpack(self.root, self.settings['sevenzip'])
    self.assertEqual((self.root / 'book.epub').read_bytes(), b'different')

  def test_split_archive(self):
    source = self.root / 'original'
    source.mkdir()
    (source / 'split.epub').write_bytes(os.urandom(5000))
    archive_root = self.root / 'archives'
    archive_root.mkdir()
    subprocess.run([self.settings['sevenzip'], 'a', '-v1k', str(archive_root / 'split.7z'), 'split.epub'], cwd=source, check=True, stdout=subprocess.DEVNULL)
    e.unpack(archive_root, self.settings['sevenzip'])
    self.assertEqual((archive_root / 'split.epub').read_bytes(), (source / 'split.epub').read_bytes())

  def test_dedup_after_consumption(self):
    source = self.root / 'book.epub'
    source.write_bytes(b'book')
    self.assertTrue(e.deliver(self.db, self.settings, source))
    next(Path(self.settings['incoming']).iterdir()).unlink()
    self.assertFalse(e.deliver(self.db, self.settings, source))
    self.assertEqual(source.read_bytes(), b'book')

  def test_recover_prepared(self):
    source = self.root / 'book.epub'
    source.write_bytes(b'book')
    with patch.object(e, 'recover', side_effect=OSError('interrupted')):
      with self.assertRaises(OSError):
        e.deliver(self.db, self.settings, source)
    e.recover(self.db, self.settings)
    self.assertEqual(len(list(Path(self.settings['incoming']).iterdir())), 1)
    self.assertFalse(e.deliver(self.db, self.settings, source))

  def test_file_list_and_category(self):
    with patch.object(e, 'api', return_value=[{'category': 'tv'}]):
      self.assertIsNone(e.torrent_sources(self.settings, 'hash'))
    torrent = {'category': 'books', 'amount_left': 0, 'save_path': self.settings['source']}
    with patch.object(e, 'api', side_effect=[[torrent], [{'priority': 1, 'progress': 0.5}]]):
      with self.assertRaises(ValueError):
        e.torrent_sources(self.settings, 'hash')

  def test_process_preserves_source(self):
    source = Path(self.settings['source'])
    (source / 'a.epub').write_bytes(b'epub')
    (source / 'a.mobi').write_bytes(b'mobi')
    with patch.object(e, 'torrent_sources', return_value=[(p, Path(p.name)) for p in source.iterdir()]):
      status, result = e.process(self.db, self.settings, 'hash')
    self.assertEqual((status, result['copied'], result['alternativesSkipped']), ('done', 1, 1))
    self.assertEqual((source / 'a.mobi').read_bytes(), b'mobi')
    self.assertEqual(list(Path(self.settings['work']).iterdir()), [])

  def test_backfill_preview_then_apply_skips_delivered_books(self):
    root = Path(self.settings['source'])
    existing = root / 'existing.epub'
    existing.write_bytes(b'already imported')
    e.deliver(self.db, self.settings, existing)
    next(Path(self.settings['incoming']).iterdir()).unlink()
    folder = root / 'new book'
    folder.mkdir()
    with zipfile.ZipFile(folder / 'pack.zip', 'w') as archive:
      archive.writestr('new.epub', b'new epub')
      archive.writestr('new.mobi', b'new mobi')
      archive.writestr('comic.cbz', b'comic')
    with patch('builtins.print'):
      preview = e.backfill(self.db, self.settings, root)
      self.assertEqual(sum(g['alreadyDelivered'] for g in preview['groups']), 1)
      self.assertEqual(list(Path(self.settings['incoming']).iterdir()), [])
      applied = e.backfill(self.db, self.settings, root, apply=True)
      self.assertEqual(sum(g['copied'] for g in applied['groups']), 1)
      repeated = e.backfill(self.db, self.settings, root, apply=True)
      self.assertEqual(sum(g['copied'] for g in repeated['groups']), 0)
    self.assertEqual(existing.read_bytes(), b'already imported')
    self.assertEqual(len(list(Path(self.settings['incoming']).iterdir())), 1)

  def test_backfill_continues_after_bad_archive(self):
    root = Path(self.settings['source'])
    (root / 'bad').mkdir()
    (root / 'bad/broken.zip').write_bytes(b'not an archive')
    (root / 'good').mkdir()
    (root / 'good/book.epub').write_bytes(b'good')
    with patch('builtins.print'):
      report = e.backfill(self.db, self.settings, root, apply=True)
    self.assertEqual(report['groups'][0]['status'], 'review')
    self.assertEqual(report['groups'][1]['copied'], 1)

  def test_backfill_rejects_outside_source(self):
    with self.assertRaises(ValueError):
      e.backfill(self.db, self.settings, self.root)

  def test_backfill_excluded_collection_is_not_extracted_or_delivered(self):
    root = Path(self.settings['source'])
    (root / 'chapter collection').mkdir()
    (root / 'chapter collection/pack.zip').write_bytes(b'not an archive')
    with patch('builtins.print'), patch.object(e, 'process_sources') as process:
      report = e.backfill(self.db, self.settings, root, apply=True, exclude=['chapter collection'])
    process.assert_not_called()
    self.assertEqual(report['groups'][0]['status'], 'review')
    self.assertEqual(list(Path(self.settings['incoming']).iterdir()), [])


if __name__ == '__main__':
  unittest.main()
