# Ebook import

Completed qBittorrent torrents in the `books` category are queued for copying into `/mnt/warez/media/ebooks/incoming`; the worker runs about every 30 seconds and preserves the originals for seeding.
Follow logs with `journalctl -u ebook-import.service -f`, inspect jobs with `ebook-import status`, or retry a failed job with `ebook-import retry <torrent-hash>` (processed on the next worker run).

For a filesystem backfill, `ebook-import backfill /mnt/warez/torrents/Books` previews selections, including archive contents. Add `--apply` to copy them into CWA's inbox. Both paths share the completion worker's lock and delivery ledger; stop the timer/worker before a long backfill and restart the timer afterward. `--limit N` processes only the first N top-level groups for a trial batch.

Inspect the preview before applying: PDF chapter packs can look like separate books. Use `--exclude 'folder name'` (repeatable) to hold a top-level collection for manual review. Pass the same exclusions on subsequent runs; exclusions are per invocation. Keep commands containing personal filenames out of repository documentation.

Backfill reports remain under `/var/lib/ebook-import/backfill-preview.json` and `/var/lib/ebook-import/backfill-report.json`. Each run replaces its corresponding report. These contain private filenames and must not be copied into Git. Ambiguous selections and archive failures stay in the report for review; a failed folder does not stop other folders. Repeating an import skips content already recorded as delivered, even after CWA has consumed the inbox copy.

## Usenet: Eweka and NinjaCentral

`SABnzbd` runs on media port 8085; `https://usenet.netcat.cloud` is routed by
Caddy and protected by the Authentik Media admins group. The backend firewall
admits only Caddy and local clients. DNS is generated from `lab/network.json`.

Root-only `/etc/usenet/credentials.json` (0600, parent directory 0700) supplies
`eweka_username`, `eweka_password`, and `ninjacentral_api_key` strings. Keep it
out of Git and the Nix store. SABnzbd API keys are generated once under its
private `/var/lib/sabnzbd` directory. Systemd loads credentials at runtime;
Nix declares all service, category, indexer, and client settings. SABnzbd's
runtime INI is writable (0600) for application state; declared settings and
runtime secrets override its saved values on each service start. Restart
`sabnzbd` and `usenet-integrations` after rotating the external credentials.

Eweka uses `news.eweka.nl:563` with strict TLS verification and 20 connections.
Downloads use `/mnt/warez/usenet/incomplete`; repaired and extracted jobs go to
`/mnt/warez/usenet/complete`. Categories mirror torrents: `movie` → `Movies`,
`tv` → `TV Shows`, `music` → `Music`, plus `books`, `audio`, `comics`, and
`software`. Default/Prowlarr jobs go to `Uncategorized`. Both folder free-space
thresholds are 100 GB; the independent download limit is 750 Mbps. Concurrent
SABnzbd and qBittorrent traffic can exceed that aggregate rate.

`usenet-integrations.service` tests and reconciles SABnzbd in Sonarr, Radarr,
Lidarr, and Prowlarr, adds NinjaCentral, and requests indexer sync. Arr apps
prefer Usenet when other release criteria tie; existing delays and custom
profiles are preserved. Seerr uses its existing Sonarr/Radarr connections.
Completed Arr downloads are removed from client history after successful
import; failed downloads can be removed and retried. Torrent clients retain
their existing seeding policy. SABnzbd does no library sorting.

Prowlarr manual grabs land in `Uncategorized` unless a category is selected;
use manual import when the relevant Arr cannot match a grab. Books/audio/
comics/software downloads currently require manual handling: the existing
book completion worker is qBittorrent-specific. Usenet ebook automation is a
separate follow-up.

SABnzbd application logs rotate natively at 10 MiB with five uncompressed
backups (about 60 MiB per stream). Native rotation owns the open file. Service
and setup output uses the existing 512 MiB persistent / 128 MiB runtime journal
cap and 14-day retention. NZB backups are disabled. A daily persistent
`sabnzbd-history-retention.timer` removes completed/failed job reports older
than 30 days, including archived reports, through SABnzbd's API with
`del_files=0`. Active jobs are excluded and rechecked before deletion. This is
age-based retention, not a hard disk quota; download folders are never swept.
After 30 days, a stranded completed download can require manual import because
its client history has expired. No automatic cleanup of library files, failed
download data, application backups, or the Nix store is performed by retention.

Rollout: build/apply media locally, then commit/push the relevant configuration.
On **pihole-dns** and **caddy**, pull that commit and run `./bin/switch` from this
repository. Caddy needs both `caddy.nix` and `authentik.nix`; both hosts need the
updated network inventory. The user performs these two remote switches.
Verify DNS resolves `usenet.netcat.cloud` to `192.168.1.203`, the frontend
requires Authentik, all four SABnzbd client tests pass, NinjaCentral is synced,
and an approved Seerr request downloads and imports into the existing library.

## Plex library updates

`plex-notifications.service` reconciles a `Plex (Nix)` connection in Sonarr,
Radarr, and Lidarr on boot and configuration changes. Imports, upgrades, and
renames notify Plex through loopback; Lidarr also notifies on track retagging.
All libraries are eligible (no tag filter), and Plex's hourly scan remains a
fallback. The apps and Plex use the same NAS paths, so no path mapping is needed.
Claim Plex before setup; its token is read from its protected preferences at
runtime and app API keys use systemd credentials, never stored in Nix.
Connection tests run before saving;
failed setup retries after 60 seconds. Inspect `journalctl -u plex-notifications`.
Setup logs go only to the existing journal (512 MiB persistent / 128 MiB runtime,
14-day retention); no additional file or job logs are created.

## Migration jobs paused

`media-import-configure.service`, `media-import-worker.service` and its timer,
and `media-import-audit-backup.service` and its timer are disabled in Nix.
Their definitions, CLI tooling, audit database, and existing backups remain
in place for later deprecation. `media-api-credentials.service` performs only
the API-key provisioning still needed by the live download integrations; it
does not apply migration policies. The independent ebook worker remains active.
# English subtitles

Bazarr runs on port 6767 and is exposed at `https://subtitles.netcat.cloud`
through Caddy and Authentik's Media admins gate. Only Caddy can reach its LAN
port. Caddy and Pi-hole deployment is manual; their minimal changes are pushed
separately so they can be pulled on those hosts.

`bazarr.nix` owns the subtitle policy. The NixOS Bazarr module has no application
settings option, so `bazarr-configure.py` merges its YAML while stopped and uses
the supported API for database-backed language profiles. Runtime Sonarr/Radarr
keys come from systemd credentials, not Git or the Nix store. The profile timer
reconciles existing media every five minutes; defaults cover new imports.

- Full embedded English subtitles, including hearing-impaired tracks, satisfy
  the profile. Forced-only and unknown-language tracks do not.
- ASS/SSA embedded subtitles also count: that format alone does not imply moving
  subtitles. Downloads use SRT and remove style tags. Videos are never rewritten;
  image subtitles and Plex client track choices can still affect positioning.
- Missing subtitles are searched every six hours. Bazarr chooses its best match
  above the default 90% episode / 70% movie score thresholds. Its own downloads
  remain eligible for upgrades every 12 hours for 30 days; manual subtitles are
  excluded from upgrades. Availability and correct timing depend on providers.
- OpenSubtitles.com and YIFY Subtitles are enabled. Gestdown and TVSubtitles are
  explicitly disabled due to provider HTTP errors.
  Enter the user's OpenSubtitles.com username/password in Settings → Providers;
  VIP privileges are determined by that account. Bazarr selects by subtitle score,
  not provider priority. Additional providers and credentials survive rebuilds.

Plex's modern language preferences belong to the account, not the server's XML
settings. Run `sudo plex-subtitles-configure` once to use the existing claim token to enable
automatic track selection, English subtitles, and Always enabled for the owner.
These account settings persist without a service or timer. The command preserves
audio-language preferences and other accounts. Manual per-item
track selections override Plex's defaults; select the external SRT if a client
continues choosing a styled embedded track. Plex's existing hourly library scan
discovers new sidecars on NFS.

Bazarr's duplicate file-log handler is disabled in the package; runtime and
provisioning logs go only to journald, capped by `common/nfs` at 512 MiB persistent,
128 MiB runtime, and 14 days, with journal compression. No debug sync job logs are
enabled. Plex keeps its existing five-archive native rotation and daily 14-day
archive cleanup. Subtitle files and database history are application data and
are not removed by log cleanup.

Check `systemctl status bazarr`, `systemctl list-timers bazarr-profiles.timer`,
and `journalctl -u bazarr-profiles`.

To backfill, open Bazarr's System → Tasks and run Index All Existing Episodes
Subtitles and Index All Existing Movies Subtitles first. Once indexing finishes,
run Search for Missing Series Subtitles and Search for Missing Movies Subtitles.
These searches respect embedded tracks and the English profile; provider quotas
can make a large backfill take multiple scheduled passes.
