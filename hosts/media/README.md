# Ebook import

Completed qBittorrent torrents in the `books` category are queued for copying into `/mnt/warez/media/ebooks/incoming`; the worker runs about every 30 seconds and preserves the originals for seeding.
Follow logs with `journalctl -u ebook-import.service -f`, inspect jobs with `ebook-import status`, or retry a failed job with `ebook-import retry <torrent-hash>` (processed on the next worker run).
