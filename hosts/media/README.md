# Ebook import

Completed qBittorrent torrents in the `books` category are queued for copying into `/mnt/warez/media/ebooks/incoming`; the worker runs about every 30 seconds and preserves the originals for seeding.
Follow logs with `journalctl -u ebook-import.service -f`, inspect jobs with `ebook-import status`, or retry a failed job with `ebook-import retry <torrent-hash>` (processed on the next worker run).

For a filesystem backfill, `ebook-import backfill /mnt/warez/torrents/Books` previews selections, including archive contents. Add `--apply` to copy them into CWA's inbox. Both paths share the completion worker's lock and delivery ledger; stop the timer/worker before a long backfill and restart the timer afterward. `--limit N` processes only the first N top-level groups for a trial batch.

Inspect the preview before applying: PDF chapter packs can look like separate books. Use `--exclude 'folder name'` (repeatable) to hold a top-level collection for manual review. Pass the same exclusions on subsequent runs; exclusions are per invocation. Keep commands containing personal filenames out of repository documentation.

Backfill reports remain under `/var/lib/ebook-import/backfill-preview.json` and `/var/lib/ebook-import/backfill-report.json`. Each run replaces its corresponding report. These contain private filenames and must not be copied into Git. Ambiguous selections and archive failures stay in the report for review; a failed folder does not stop other folders. Repeating an import skips content already recorded as delivered, even after CWA has consumed the inbox copy.
