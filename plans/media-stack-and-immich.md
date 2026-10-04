# Media stack, Whatbox migration, and Immich

Status: initial import stack and incremental audit tooling implemented on 2026-10-01. Whatbox rsync transfer was reported complete. Library imports require saved terminal batch approvals; batch 1 imported five movies, and their Radarr identities, exact paths, and source hardlinks were independently verified on 2026-10-02. Local seeding remains deferred. The implementation notes below supersede earlier workflow details where they differ.

## Implemented incremental audit workflow

`hosts/media/import-stack.nix` declares Sonarr, Radarr, Lidarr, Audiobookshelf, and the `media-import` CLI. All four applications accept local API connections and connections from Caddy through a source-restricted firewall rule; other LAN clients cannot connect directly to their backend ports. A Nix-managed initializer sets migration safety options via the applications' APIs, generates local login credentials, and supplies private API-key files. Application state and the audit database stay on the VM disk.

The actual mount is `/mnt/warez`, backed by `truenas.vm.netcat.cloud:/mnt/warez/data`. Keep `/mnt/warez/torrents` unchanged. Library directories are ordinary directories under `/mnt/warez/media`: `movies`, `tv`, `music`, `audiobooks`, `podcasts`, and `alternates`.

The shared NFS module disables idle unmounting (`x-systemd.idle-timeout=0`) for both Media and Panther. The former ten-minute timeout was confirmed to stop Media's dependent applications before unmounting the share. Automounting and mount-presence checks remain enabled; an idle share stays mounted.

### Subtitle backfill

On 2026-10-04, user-authorized batch 55 hardlinked and verified 401 companion
files for 160 imported movies/episodes: 193 SRT files and 104 VobSub IDX/SUB pairs.
Their current audit status is `verified-companion`; prior exclusions remain
historical. Each file has a SHA-256 baseline, parent-operation evidence, and its
exact destination in the batch manifest. Names use the actual library video stem,
language metadata, and distinct labels for Star Wars variants. Multilingual
VobSub pairs retain their internal language streams. Source names and contents,
including subtitle encodings and timing, were not modified.

Five EverQuest disc-image `.sub` files remain excluded, as does the Red Dwarf
S01E01 LATENCY subtitle pair: its specific source video was superseded, so those
subtitles were not attached to the different imported release.

`python -m media_import.companion_backfill PLAN.json` validates an explicit plan;
`--apply` backs up the audit database, records approval atomically, and uses the
existing resumable importer. It checks verified parents, source metadata,
hardlinks, paired filenames, and destination collisions. A remounted NFS device
number is recorded as a new subtitle revision only when all other signature
fields match and the configured export is mounted. Reapplying the same plan
resumes its recorded batch. This tool does not discover future subtitles.

### Records and incremental behavior

The authoritative database is `/var/lib/media-import/audit.sqlite`, owned by `dbalatero`. It records source paths, immutable file revisions, probes, metadata lookup evidence, proposals, decisions, approved manifests, operations, and verification history. The database is not stored on NFS. Runtime credentials in this directory are secrets, not repository files.

- Inventory scans register new paths and update observations without re-probing or rehashing unchanged files. A new file must have two unchanged observations at least ten minutes apart before proposal generation. This is a stability heuristic; batch approval also requires confirming transfers are finished.
- Changed source metadata produces a new revision. Existing approval no longer applies. Files touched after an import operation began are held for investigation rather than automatically requeued.
- Missing files are recorded only after a complete successful scan. No library file is deleted. Mount mismatches, traversal errors, symlinks, and partial transfers fail closed or remain explicit exceptions.
- A verified operation is skipped on subsequent `apply` runs, including application calls. `verify` rechecks source metadata, destination ownership (hardlinks or music copies), and application assignments; `verify --hash` additionally reads file contents.
- `propose` performs local ffprobe/filename analysis and queries the local Radarr, Sonarr, or Lidarr APIs. Metadata responses are cached. No per-file LLM calls are used. Audiobook proposals use existing tags and explicit author/title/order review.
- Source paths are separate records even if content is identical. Alternate imports must be explicitly selected; content hashes are optional investigation evidence.

### Music review

Run `media-import run --kind music --limit 50`. Review groups pending tracks by
album source folder. Immediate `CD1`/`CD2`, `Disc 1`/`Disc 2`, and `Disk1`/`Disk2`
subfolders share one review, while separate album/copy folders stay separate.
Disc folder numbers supply missing disc tags; conflicting explicit tags block
approval. The file limit expands to finish selected album folders; explicit `--files` filters still
apply. `run` prepares any remaining eligible tracks in those folders. `review`
uses only prepared proposals. Deferred, previously selected, imported, and unstable
files are not silently added to the group.

Choose the artist/album once for every pending track in the source folder, even
when individual tracks returned different or empty search results. Each track
keeps its own local title, duration, and disc/track numbering for the release
comparison; the folder is approved together or left unapproved. Then choose an
edition labeled by format, edition date, country, track count, record label, and
disambiguation. Edition dates come from the MusicBrainz release API joined by exact
release ID and cached in SQLite for 30 days; identities and tracks still come from
Lidarr. Unavailable dates show as unknown, never the original album year. Date
lookup failures leave review usable. Menus show the page count. Menus use single keys with `n`/`p` for pages and `v` for
full details. Confirm loading metadata into Lidarr: this registers an unmonitored
artist and selects the album release, but does not import files or enable searches.
That catalog state may remain if the review is deferred or quit. The intent is
recorded in SQLite before the API mutation. Lidarr search alone has no track list;
registered release tracks are fetched using its supported track API.

The comparison shows local and expected track titles/durations at each disc/track
position and the destination paths. A complete, continuously numbered vinyl rip
can map across side labels (for example, local 1–4 to two records labeled A–D).
This requires explicit confirmation of the displayed titles and durations; partial
rips and ambiguous positions remain unresolved. Import follows the approved
MusicBrainz track IDs and rechecks their metadata, preserving local numbering. It records MusicBrainz track and recording IDs,
release metadata, and comparison warnings per file. Missing/ambiguous track IDs or
duplicate disc/track positions block group approval. Titles ignore punctuation,
case, and accents; duration differences above three seconds or two percent
(whichever is larger) are flagged. Missing comparison evidence and track-count
differences are also flagged. Warnings require explicit `y`; otherwise Enter saves
the entire displayed group atomically. This is metadata comparison, not audio
fingerprinting. Existing approvals are unchanged.

`d` defers the folder; `q` saves prior decisions and exits; `i` at the album/edition
menu proceeds to the final import preview for previously saved selections. Final
import still requires explicit `y`. Apply rechecks saved track metadata before
linking, and verification checks the exact file association and track identity.
Matching evidence lives in SQLite and application records.
Music imports now use independent copies. Lidarr synchronizes embedded tags on
those copies; tag scrubbing and cover embedding remain disabled. Only the music
library is writable by Lidarr; torrent sources and other libraries remain
read-only. Source filenames and bytes remain unchanged.

### Music throughput and background queue

Music-only `run` and `review` sessions (`--kind music`) now enqueue explicitly
approved batches instead of waiting for import. `media-import queue` shows the last
20 jobs, completion percentages, and errors. `media-import-worker.service` drains
the durable SQLite `import_jobs` queue; its timer checks every 15 seconds. Jobs
interrupted while running resume at their saved checkpoints. Failed jobs stop
retrying and show `media-import apply BATCH` for a deliberate resume after repair.
Previously approved batches are not silently enqueued. Mixed-category sessions
and explicit `apply` remain synchronous.

Review and the music worker use separate process locks with shared coordination;
other CLI operations keep exclusive coordination. Source music files are read-only
in both paths. A short-lived catalog lock prevents review from changing release
selection during an album import; loading a new preview can briefly wait for the
current album. Each file retains its own approval and verification record. Artist
metadata refresh runs once per artist per batch, copies are staged per file, and
one ManualImport command registers the pending tracks in an album together. Command
polling is every 250 ms, removing the old fixed two-second wait per command.

The named `Existing library import` metadata profile includes all primary and
secondary album types and release statuses, including live/bootleg recordings.
It is assigned to artists explicitly prepared by the importer; existing standard
profiles are untouched. Monitoring, search, indexers, and download clients remain
disabled, so metadata inclusion does not authorize downloads.

Artist refresh can finish before album releases and tracks are populated. The
importer waits for the exact selected release and its complete track list, with
one targeted album refresh when needed. It never substitutes another edition;
a metadata timeout leaves the folder available for another review.

The worker writes only to the system journal, covered by Media's existing shared
NFS module policy: 512 MiB persistent journal, 128 MiB runtime journal, and 14-day
maximum retention. It creates no per-job log files or extra cleanup directories.

### Independent music copies and tagging

Music alone is copied, including already-approved batches. Other categories
continue to use hardlinks. Each copy streams to an operation-owned temporary file
in its destination directory, verifies its initial SHA-256 against the bytes read
from the stable source, and publishes only the completed file. The `music_copies`
ledger records staging, publication, initial hash, and destination inode separately
from the immutable source manifest. Interrupted copies resume or recreate their
recorded partial staging file; unrelated destination files are never overwritten.

After publication, Lidarr may change the independent copy's tags. Verification
checks source stability, independent destination ownership, and exact approved
track assignment, not byte equality between a retagged copy and the torrent.
Verified source operations remain terminal and are skipped on later apply/runs.
Explicit `verify --hash` compares the torrent source with its saved source hash.

For the one-time conversion, stop Lidarr and the policy initializer, run
`media-import migrate-music-copies`, then apply the updated Nix configuration.
The conversion preserves the original manifests, records the transition, replaces
only recorded music hardlinks with verified copies, and updates the source ctime
checkpoint after unlinking. It checks once that no library hardlinks or symlinks
remain. There is no permanent whole-library startup scan.

Lidarr receives the approved artist, album, release and track IDs via ManualImport,
with replacement disabled and the destination already inside its artist folder.
Music root registration and `writeAudioTags = sync`, `copyUsingHardlinks = false`
are declared through the Nix-managed initializer. Monitoring/acquisition remain
disabled. Lidarr retains existing bounded NLog archives and journal retention;
the background import worker adds no standalone log files. Incomplete staging files are preserved
for resume, not subject to log cleanup.

### Background hash cache

Hashing is optional and is not a prerequisite for import. On Media, run
`screen -S media-hash`, then `media-import hash`. Detach with Ctrl-a followed
by d; return with `screen -r media-hash`. An already-running worker can continue
through CLI upgrades without being restarted. Ctrl-C stops the
worker, preserving completed hashes. Rerunning skips valid cached hashes and
all files with import operations, including completed imports. The unfinished
file is restarted. The worker processes the stable files in the current
inventory; run `inventory` after later downloads, and observe new files twice
at least ten minutes apart before hashing them.

The display reports a byte-weighted queue percentage, current-file percentage,
read throughput, and estimated remaining time while large files are read. Queue
progress includes files checked and skipped; the final counters distinguish
cached, newly hashed, changed/skipped, and failed files. `hash --kind movie tv`
limits categories and `hash --limit 10` limits the number of files checked.
The worker writes no standalone log file; tmux retains bounded terminal history.

SHA-256 values are stored in the audit database's `hashes` table, bound to the
revision and exact size/mtime/ctime/device/inode signature. The worker hashes
outside the audit lock and rechecks source and database state under the lock
before publishing each result. Review and imports can proceed concurrently;
the worker waits for their lock before saving. It never imports or changes media.

Normal hardlink `apply` and `verify` do not hash file contents, including recovery of an
interrupted hardlink operation. They check the recorded source signature,
hardlink identity, and application assignment. Available cached hashes may be
recorded for later investigation, but there is no automatic duplicate-content
block based on whether the optional worker happened to finish a file.

Use `media-import verify BATCH --hash` only when a content audit is wanted. It
compares against a saved SHA-256 baseline, or clearly reports that it is creating
the first baseline when none exists. A first hash cannot establish historical
integrity. Metadata checks assume filesystem change reporting works; they do
not detect silent storage corruption. Hash records remain in SQLite backups
and CSV exports. A crash between linking and recording the new ctime can resume
when the saved preparation, size, mtime, device, inode, and existing hardlink
agree; a full content audit is available separately.

### Commands, run on Media as dbalatero

Run the guided workflow:

```bash
media-import
# Or focus the next small queue:
media-import run --kind movie --limit 10
```

This refreshes inventory, prepares up to ten review records, shows the matches,
and offers to import the saved selection in the same session. No proposal IDs
or batch IDs need to be copied. New files still need two unchanged observations
at least ten minutes apart, so newly discovered files become eligible on a later
run. Existing verified imports remain closed.

In a terminal, menus read a single key without requiring Enter:

- Select a candidate by number (`0` selects the tenth candidate). Enter selects
  the candidate only when exactly one is offered. Then Enter keeps the displayed
  identity, episode/track assignment, and destination.
- `v` shows supporting evidence; `e` edits the mapping; `d` defers; `x` excludes.
  Deferrals/exclusions save a default reason immediately; `reopen FILE_ID` allows
  explicit later correction. `g` previews a season/album/book group from the
  current queue; music requires choosing a specific release.
- `i` finishes reviewing early and shows the import preview. `q` saves and exits
  without importing. Ctrl-C also keeps already saved decisions.
- At the final exact batch preview, press `y` to import and verify, confirming
  that transfers for those files are finished. Enter or `n` saves the selections
  for later without importing. No typed confirmation words are required.
- Saved selections are offered on the next run and shown in full before import.
  The preview is scoped to any supplied `--files` or `--kind` filter.

`media-import review` uses the same flow for already prepared proposals without
rescanning or generating more. The older `inventory`, `propose`, `approve`, and
`apply` commands remain available for diagnostics and automation. Approval is
still an immutable database checkpoint, followed automatically by execution in
the guided flow. A failed batch prints its `media-import apply BATCH` resume
command. Completed operations are skipped when resuming.

Normal `apply` already verifies library files and app assignments; there is no
need to run `verify` again immediately. `media-import verify BATCH` is a later
metadata/app check, and `media-import verify BATCH --hash` adds a full content
audit. `media-import backup` and `media-import export DIRECTORY` remain available.

For focused investigation, `media-import list --kind movie --contains Brazil` finds stable file IDs and outcomes; `media-import show FILE_ID` shows their observations, proposals, decisions, and operations. CSV exports include a joined `current.csv` with one row per source path, its current outcome, destination, identity, reason, and recorded hash. `propose --files FILE_ID --kind KIND --retry` regenerates an unreviewed proposal, optionally with `--refresh-metadata`; it does not reopen decisions or completed imports. `reopen FILE_ID` explicitly edits a previously reviewed mapping while preserving history and refuses files with existing import operations. Difficult corrections after an operation began need investigation of that operation; there is deliberately no bulk reset/delete command.

Archive work stays separate: `propose --kind archive --files FILE_ID ...` records member listings without extraction. Do not approve an archive as a media file. The known movie/TV/music exceptions include five Conan RAR releases, Malcolm in the Middle season-one ZIP, Prison Break subtitle RARs, The Threepenny Opera FLAC ZIP, and a misplaced software ZIP. Other categories remain inventoried even though ebook/comic/software application management is deferred.

### Execution and verification

Implementation adjustment: the importer registers approved identities unmonitored through supported app APIs, creates the approved library files itself, and verifies the app assignments. Non-music categories use hardlinks without a fallback copy. Music uses verified independent copies and explicit Lidarr track registration. Lidarr can write only to the music library, with tag synchronization enabled; torrent originals and other libraries remain read-only to it. The other apps retain read-only NAS access. Application databases stay local.

Every approved manifest has a digest and specific source revision IDs. The executor revalidates decisions, source observations, and destination collisions; backs up app state; records an exact-signature cached SHA-256 when available without requiring one; records progress before side effects; and checks both inode identity and the app's movie/episode/track assignment before marking an operation verified. A crash after creating a hardlink can be reconciled using the recorded preparation and matching file identity/metadata. Failed app matching leaves a recorded linked-but-unverified operation for correction, never a false success. No source move, deletion, permission rewrite, tag modification, or automatic extraction is performed.

The first real movie pilot is complete: batch 1 contains 20 Days in Mariupol, A Few Good Men, A Goofy Movie, A Separation, and Alien. All five were confirmed in Radarr with matching hardlinks. Music batch 17 also completed on 2026-10-03: 13 Siamese Dream tracks and 12 Calling Out of Context tracks were imported as independent copies, assigned to their approved Lidarr tracks, and tagged. All 25 torrent originals matched their saved SHA-256 baselines afterward; repeating apply was a no-op. TV and multidisc music still need pilots. Cover a flat movie, a movie with companions, a TV season, single/multidisc music, and single/multipart audiobooks. Synthetic filesystem tests do not establish that the real collection has been correctly matched.

### Hardcore History repair

The first Audiobookshelf pilot exposed two issues: a scan returned before the
new file was registered, and generic album tags grouped unrelated podcast
episodes into one `dancarlin.com` book with duplicate part numbers. The scanner
now waits for the exact audio path; batch validation rejects duplicate part
numbers within a shared book before applying anything.

Hardcore History proposals now use the `dchhaNN - Title` filename for individual
episode entries, with Dan Carlin as author and `Hardcore History` as a numbered
Audiobookshelf series. Each entry has one audio file, at part 1. Series sequence
and title are set and verified through the app API, without modifying audio tags.

`media-import repair-hardcore-history 2` is the scoped, user-authorized repair
for the early generic-album mappings. It preserves the original manifest and
operation snapshots, creates a new repair batch, marks the replaced operations
superseded, and verifies every new entry before unlinking the obsolete library
names. It removes the obsolete Audiobookshelf record with filesystem deletion
disabled, preserves its metadata snapshot in the audit log, and resumes the
remaining approved original-batch work. Backups precede the repair. The command
can resume/repeat without creating additional repair batches. Only the original
library hardlinks are removed; torrent paths and payloads are preserved.

### Podcasts naming and filename variants

The former `/mnt/warez/media/spoken-word` directory is now
`/mnt/warez/media/podcasts`; its Audiobookshelf library is named Podcasts.
`media-import migrate-podcasts` moved the directory and used an overlapping-folder
scan to retain all eight item IDs, then removed the obsolete library-folder
registration after verifying every item belonged to the new folder. Audiobookshelf
library type remains `book` to retain the chosen individual-episode/series layout;
no RSS subscriptions or automatic downloads are introduced.

The audit database records the relocation separately in `meta.library_relocations`
and migration events. Historical manifests/proposals and their digests are not
rewritten. Current review, import, reports, and verification interpret their old
paths through this recorded relocation. Original torrent paths are unchanged.
The inventory category is now `podcast`, and Nix creates the podcasts root.

Both `dchhaNN - Title.mp3` and `dchhaNN_Title_.mp3` filename patterns are supported;
underscores become spaces and trailing separators are discarded. All 54 existing
Hardcore History paths parsed successfully. Ten unresolved proposals were
regenerated without altering saved decisions or approving new imports. The
migrated eight files were reverified and the audit database backed up to the NAS.

### Access, backups, and logs

The internal HTTPS names are `tv.netcat.cloud` (Sonarr), `movies.netcat.cloud` (Radarr), `music.netcat.cloud` (Lidarr), and `audiobooks.netcat.cloud` (Audiobookshelf). DNS and Caddy routes are generated from `lab/network.json`. Media allows backend connections from Caddy (`192.168.1.203`) only, plus localhost for the importer. Caddy and Pi-hole deployment must be completed on their respective machines; see the ordered handoff in `lab/caddy.md`. No public service address records or WAN forwarding are needed.

Until that deployment is complete, SSH forwarding remains available:

```bash
ssh -N -L 7878:127.0.0.1:7878 -L 8989:127.0.0.1:8989 \
  -L 8686:127.0.0.1:8686 -L 8000:127.0.0.1:8000 dbalatero@media.vm.netcat.cloud
```

The initialized username is `dbalatero`; private generated passwords are `/var/lib/media-import/{radarr,sonarr,lidarr,audiobookshelf}.password`. Read them locally when needed; do not paste them into chat or Git. API keys are separate files. The initializer does not reset an existing Audiobookshelf account.

SQLite online backups are taken locally after review/approval and before imports. `media-import backup` copies a consistent snapshot to `/mnt/warez/media-import-audit`; a daily Nix-managed timer also does this. Keep migration history and backups through handover; these are persistent audit artifacts, not disposable logs. Backups on the same NAS are not an independent failure-domain backup.

Journald uses the existing 512 MiB persistent / 128 MiB runtime / 14-day limits. Servarr uses native rotation, explicitly configured for ten 1 MiB archives per enabled level, with info logging and its separate log database disabled. Audiobookshelf daily and scan logs older than fourteen days are removed by a timer; this is age-based, not a strict quota. Crash logs rotate daily or when checked above 10 MiB, with seven compressed rotations. Log cleanup never deletes application databases, media, or Nix packages.

Validation includes 94 passing tests via `python3 -m unittest discover -s tests/media_import -v`, a live single-key quit smoke test, a no-hash recheck of all five batch-1 movies, Nix evaluation/build, actual service/API checks, and a temporary NAS hardlink readable by all four service identities. The initial live inventory found 16,471 files without scan errors. Actual collection import, real-match verification, and future torrent rechecks remain separate milestones.

Later pulls must preserve relative paths and avoid `--inplace` and `--delete`. Run inventory/propose/review again after each completed pull; completed imports remain closed. Preserve original torrent metadata and save-root semantics. A future local client must force-recheck each torrent to 100% before seeding.

## Current priority: correctly import existing media through hardlinks

Prerequisite completed in the repository on 2026-10-01: `lab/network.json` now separates `machines` from `services`. Each service has a stable `name`, frontend `hostname`, backend `machine`, `scheme`, and `port`. DNS and Caddy consume the same entries, so Media can host several frontend names. Only the four existing services were migrated; no Media service routes have been added. Generated DNS records and Caddy virtual hosts were compared with their pre-refactor output and are unchanged. See `lab/README.md` for the schema. This is a configuration refactor, not a live deployment.

The user has repeatedly been unable to turn existing release folders into a correctly matched, organized library with the *arr apps. Solving that workflow is the immediate objective. A running service or a completed folder scan is not success: the correct movie/episodes must appear at the intended library paths as verified hardlinks, with original torrent payloads preserved.

Bootstrap Sonarr and Radarr first and prove this using the already-synced collection. GPU userspace work, Plex deployment, Immich, books/comics, new downloads, tracker/indexer integration, and active local seeding are deferred until the import workflow succeeds. These remain long-term goals. Prowlarr is part of the eventual stack but is not a prerequisite for importing local files. Metadata-provider access is still needed to identify and add titles.

### A. Inspect the real collection and prove storage access

- Inspect the current Media configuration, actual NAS export/mount, and the transferred source paths. Do not assume that every directory in the target layout already exists.
- Produce a read-only inventory of movie and TV files with relative paths and sizes. Identify flat releases, season packs, nested folders, archives, samples/extras, subtitles, duplicate editions, and incomplete files.
- Select a small representative pilot: an unambiguous movie, a movie with an ambiguous title/year or edition, a straightforward TV episode, and a messy season pack where available. Include a previously troublesome example if the user can identify one.
- Finish only the storage prerequisites needed for this pilot: one `/data` mount, group/ACL access, library destination directories, and mount dependencies. Verify creating a hardlink as the actual importer service identity, not merely as root or `dbalatero`.
- Account for NFS server-side permissions and hardlink protection checks. A source being readable does not alone prove that the service can hardlink it. Inspect actual errors; do not broadly chmod/chown the collection or disable protections as a shortcut.

### B. Bootstrap the importers without acquisition automation

- Declare Sonarr and Radarr in Media's NixOS configuration with local application state, controlled LAN access/authentication, correct service memberships, and bounded logs.
- Set separate destination roots: `/data/media/movies` and `/data/media/tv`. Never register the raw torrent tree as the managed library root.
- Enable hardlinks and establish naming templates before the pilot. Include title/year and supported stable identifiers in folder names where useful; preserve useful quality/release details in file naming.
- Add titles unmonitored, leave upgrades disabled for the migration profiles, and do not trigger searches or connect acquisition automation yet. Do not configure source-removal cleanup.
- Distinguish adding a movie/series to the app's database from importing its files. Raw release folders need interactive/manual import into an already identified title; existing-library import alone does not solve this migration.

### C. Build and review an explicit matching proposal

For each pilot release, record source paths, proposed destination paths, canonical title/year, provider identity (TMDb movie ID or Sonarr's TVDb series ID), and the evidence for the match. For TV, record every source file's season/episode assignment and expected episode title, including any multi-episode mapping.

Use filenames and folder names as clues, not proof. Reconcile remakes, regional variants, specials, anime/absolute numbering, alternate episode ordering, and edition duplicates against metadata and file contents when necessary. Media duration or a targeted manual preview can help resolve ambiguity. Keep an explicit unresolved list; do not force low-confidence matches merely to finish a batch.

Review the app's interactive import preview against that proposal before writing library entries. Correct movie/series and episode assignments there. If the app cannot represent a release or multiple editions cleanly, document the limitation and choose a deliberate handling strategy rather than overwriting a valid library file. Matching scripts or API helpers may assist later, but their proposals must remain inspectable and must use the pinned app's supported interfaces.

### D. Import and verify the pilot

- Record a source manifest before import. Content hashing is optional; the current workflow above uses metadata, inode identity, and application checks. Snapshot/backup importer state before a batch so incorrect metadata assignments can be recovered.
- Import with the explicit copy/hardlink mode, never move mode. Verify the installed app version's actual behavior; a setting named "use hardlinks" can still fall back to copying.
- Compare source and destination `stat` data from the same client mount: device and inode must match and link count must reflect the additional name. File size equality alone is insufficient. If the app copied, stop expansion and diagnose mounts, permissions, or import mode.
- Confirm source filenames, paths, sizes, and modification times match the pre-import manifest. Use the optional full hash audit when investigating content integrity; a new hash without a previous baseline cannot prove historical integrity.
- Verify each movie/episode assignment in Sonarr/Radarr and the physical destination naming. Check for omitted episodes, samples accidentally imported as episodes, unwanted duplicate replacements, and correct subtitle handling.
- Rescan the organized library and repeat the import preview to check that the app recognizes existing imports instead of duplicating or replacing them unexpectedly.
- Preserve source payloads during correction. Remove or relink only reviewed destination entries and correct app state; do not use a bulk delete operation that could include the download source.

Archived payloads are an explicit exception: extracted video is separate data, so retaining RARs plus video consumes additional space. Report these separately from ordinary hardlink imports. No content rewriting or repacking of seeded originals.

### E. Expand only after the pilot passes

Carry the same source-to-title/episode-to-destination mapping into small batches. Keep counts of discovered files, matched titles/episodes, verified hardlinks, deliberate exclusions, archive extractions, and unresolved cases. Reconcile every candidate file to an outcome rather than equating an empty import queue with a complete library.

The deliverable is a correctly organized existing movie/TV library plus a repeatable, documented import workflow and an explicit exception list. Do not promise that every ambiguous release can be matched automatically. Additional confirmation is needed only for genuinely ambiguous identity/edition decisions; routine high-confidence batches can follow the verified workflow.

## Goals

- Bring the existing Whatbox collection home to TrueNAS with resumable transfers.
- Preserve torrent payload names, directory structure, and original torrent metadata so the collection can seed from the home connection.
- Build a separate, correctly matched movie/TV library for Plex without duplicating unmodified video files.
- Run local torrent and Usenet downloading with Sonarr, Radarr, and Prowlarr.
- Manage ebooks with Calibre and provide comic browsing/reading, provisionally with Komga.
- Run Immich for personal photos/videos, including accelerated video processing and machine learning.
- Share storage with the media VM, other Linux VMs, and the desktop; retain the option of SMB access.
- Declare NixOS services, mounts, drivers, permissions, and retention in this repository. Keep secrets out of Git and the Nix store.

## Current state and accepted decisions

### Host and VM resources

The Proxmox host has an AMD EPYC 4545P, 16 cores/32 threads, and 64 GB ECC RAM. Earlier MCP metrics reported approximately 60.42 GiB usable RAM.

| VM | ID | vCPUs | Configured RAM | Notes |
|---|---|---|---|---|
| TrueNAS | 100 | 4 | 20 GiB fixed | Existing storage VM, VirtIO on vmbr0 |
| Pi-hole | 101 | 1 | 2 GiB | DNS at 192.168.1.202 |
| Caddy | 102 | 2 | 4 GiB | Existing reverse proxy |
| Builder | 103 | 8 | 8 GiB maximum, 4 GiB balloon minimum | Resize confirmed through MCP on 2026-10-01 |
| Media | 104 | 8 | 16 GiB fixed, ballooning disabled | Configuration confirmed through MCP on 2026-10-01 |

The maximum guest allocations total 50 GiB, leaving approximately 10.4 GiB for the host, virtualization overhead, and caching. Balloon minimums are targets, not guaranteed sufficient working memory. The user explicitly accepted keeping Builder's existing concurrency: two package builds, four cores per build, two sandbox build users. Do not lower it as part of this work.

Media was cloned from template 9000. Live configuration confirms:

- CPU type `host`, one socket, eight cores; q35 and OVMF/UEFI.
- 200 GiB `scsi0` on `vm-storage-containers`, using `virtio-scsi-single` and an I/O thread.
- VirtIO NIC on `vmbr0`, with Proxmox firewall enabled; guest agent and autostart enabled.
- Serial console retained; `hostpci0: 0000:03:00.0,pcie=1`.
- Thin provisioning is preferred, but the storage's actual reservation policy and end-to-end discard still need verification. A full clone means independent disks, not necessarily full space reservation.

Repository configuration exists at `hosts/media/configuration.nix` and `home/hosts/media/`. Media is recorded at `192.168.1.205` in `lab/network.json`; its intended direct name is `media.vm.netcat.cloud`. Verify live DNS and guest filesystem growth; do not repeat cloning/bootstrap.

### GPU

The GPU is a dedicated Intel Arc A380 (`8086:56a5`), not Intel integrated graphics. User-provided host output showed PCI address `03:00.0` alone in IOMMU group 16. ASPEED and AMD integrated graphics remain available to the host.

User-provided output inside Media confirms:

- Arc A380 visible at guest PCI address `01:00.0`.
- Kernel driver `i915` loaded.
- `/dev/dri/card0` and `/dev/dri/renderD128` present.

Passthrough and the guest kernel driver work. Userspace media/OpenVINO drivers, service access, actual transcoding, and actual GPU inference are NOT yet verified. The displayed render node was world-readable/writable; use durable service/device configuration rather than relying on that incidental mode.

One VM owns the physical GPU; Plex and Immich share it as applications within that VM. If containers are used, expose the render device to each relevant container and configure permissions there. GPU access is distinct from the `media` filesystem group.

### TrueNAS identity and permissions

TrueNAS is `192.168.1.201` (`truenas.vm.netcat.cloud`). Its pool root is `/mnt/warez`; the user created child dataset `warez/data` at `/mnt/warez/data`.

- `dbalatero` was created with UID 1000, its own primary group, and supplementary `media` membership.
- Shared group `media` uses GID 2000; SMB Group was selected for potential future SMB use.
- `truenas_admin` remains the administrator. Regular file access does not require granting `dbalatero` Full Admin or sudo.
- Shared NixOS media-group configuration is in `hosts/common/media.nix`; managed Macs have the corresponding Darwin module. Applying it to each machine is separate from declaring it.

The final POSIX ACL editor showed owner `root`, owning group `media`, and ten entries:

| Entry | Access ACL | Default ACL |
|---|---|---|
| User Obj | rwx | rwx |
| Group Obj | rwx | rwx |
| Other | none | none |
| Named Group: media | rwx | rwx |
| Mask | rwx | rwx |

The user successfully created and deleted a file as `dbalatero` in the dataset. Its ownership was `dbalatero:dbalatero` with an ACL (`+` in `ls`). Named default `media` entries are intended to grant media-group access regardless of the owning group; setgid is not required for that strategy. Verify actual inherited ACLs and cross-user writes before bulk import. Default ACLs affect new content; copied modes, chmod, and applications that request restrictive permissions can limit effective access.

## Target storage layout

Use one export of `/mnt/warez/data` mounted at `/data` inside Media:

```text
/data/                          # one NAS dataset and one client mount
  torrents/                     # preserve original Whatbox layout here
    Audio/
    Books/
    Comics/
    Movies/
    Music/
    Software/
    TV Shows/
  usenet/
    incomplete/
    complete/
  media/
    movies/
    tv/
    comics/
```

The user chose to avoid a `torrents/whatbox` versus `torrents/local` split. Synced payloads can become the local client's permanent seeding data. Match each torrent's original save-root semantics rather than assuming every torrent has a top-level folder.

`torrents` and `media` must be ordinary directories in this single dataset. Hardlinks do not cross ZFS datasets, even in the same pool. Containers running importers should see the source and destination through one `/data` mount. Verify same-device/same-inode links using real imports and service identities; do not infer hardlink success from a successful copy.

Personal photos should use a separate NAS dataset/export mounted at `/photos`, with separate ownership, permissions, snapshots, and backup policy. This is proposed, not created. Downloaders must not receive write access to personal photos. No cross-dataset hardlinks are needed between photos and downloaded media.

Keep PostgreSQL, other application databases/configuration, Plex metadata, and ML model caches on the VM's SSD-backed disk. Bound local transcode scratch use. Local Usenet repair/extraction scratch is optional: moving its completed files to the NAS requires a copy. Decide where Immich thumbnails and encoded videos live based on library size and local disk headroom.

Calibre's live library includes its database alongside the books; do not put that live library on NFS. Start with a local VM library and back it up to the NAS, or choose a host with direct local access to its storage. This differs from merely storing ebook originals under `torrents/Books`.

## Supporting workstreams and deferred goals

The current-priority sequence above governs execution. The sections below retain storage details and the broader roadmap; their order does not make GPU setup or deployment of the full stack a prerequisite for existing-media imports.

### Storage access and mount lifecycle — immediate prerequisite

- Configure a TrueNAS NFS export for `warez/data` to the intended clients. Use normal numeric UID/GID access, preserve individual identities, leave Mapall unset, and retain root squashing.
- Declare the guest mount in NixOS. Start with NFSv4.1/TCP, hard mounting, and negotiated transfer sizes. Benchmark default connectivity against `nconnect=4` only if throughput warrants tuning; do not assume more connections are faster.
- Both VMs already use VirtIO on vmbr0. Traffic stays within the host when they share bridge/VLAN/subnet; physical LAN speed still matters for desktop clients.
- Make dependent services require the mount and verify its presence before writing. An absent NAS must not cause applications to populate the VM's underlying empty `/data` directory. Test outage/recovery and startup behavior.
- Check group 2000 in guests and containers, ACL inheritance, actual service write access, and a hardlink from a temporary torrent file to a temporary library path. Plex should receive read access to media; only necessary writers join `media`.
- Optional SMB access is a later share configuration, not enabled merely by marking the group as SMB-capable. Recheck permission behavior if configuring multiprotocol access.

### Intel userspace drivers and GPU validation — deferred

- Inspect the pinned nixpkgs/NixOS options and configure Intel Arc media and compute userspace support declaratively. Kernel passthrough is already complete.
- Validate supported video profiles with appropriate tools, then test a representative hardware transcode. Verify hardware activity rather than relying only on device visibility.
- Configure Plex hardware acceleration and confirm Plex Pass availability. Test actual playback, including desired HDR-to-SDR behavior and subtitle cases, which can still involve CPU work.
- Configure Immich video acceleration through QSV/VAAPI and ML acceleration through OpenVINO independently. Confirm actual inference uses the GPU, rather than silently falling back to CPU.
- Start with modest background-job concurrency. Test simultaneous Plex playback and Immich processing before increasing it.

### Application stack — Sonarr/Radarr first, remaining services deferred

| Service | Purpose |
|---|---|
| qBittorrent | Local downloading and seeding; proposed client |
| SABnzbd | Usenet downloads, repair, extraction; proposed client |
| Prowlarr | Tracker/indexer management and synchronization |
| Sonarr | TV matching, acquisition, naming, and import |
| Radarr | Movie matching, acquisition, naming, and import |
| Plex | Playback from the organized media library |
| Calibre | Ebook metadata, conversion, library, and optional content server |
| Komga | Proposed comic library/reader; not a comic acquisition manager |
| Immich | Personal photo/video library, uploads, search, and recognition |

Use modules imported by `hosts/media/configuration.nix` for system services. Prefer native NixOS modules where suitable; decide native services versus declaratively managed containers after checking the pinned packages and Immich deployment requirements. Pin container versions if used. Do not install the stack imperatively.

Provider server credentials go into SABnzbd; Usenet indexer keys and torrent tracker access go into Prowlarr. The user has credentials, but provider versus indexer coverage still needs confirmation. Connect Sonarr/Radarr to both clients with separate app categories. Establish quality profiles and retention/seeding rules before enabling automatic acquisition. Preserve original torrent data from automatic cleanup during migration.

Store credentials through supported runtime secret files/credentials, never Nix string literals committed to Git. Add LAN access and selected Caddy routes through the existing network inventory/proxy pattern. Choose service aliases, remote access, and authentication deliberately; do not expose every administration UI publicly. Document unavoidable application-managed state and back it up.

### Whatbox transfer — reported complete; verification remains

Whatbox source: `dbalatero@pumpkin.whatbox.ca:files/`. Original categories are Audio, Books, Comics, Movies, Music, Software, and TV Shows. Preserve non-video categories even if their application management is deferred.

The command already provided to run on TrueNAS as `dbalatero` is:

```bash
mkdir -p /mnt/warez/data/torrents
rsync -rtvh \
  --partial-dir=.rsync-partial \
  --info=progress2 \
  dbalatero@pumpkin.whatbox.ca:files/ \
  /mnt/warez/data/torrents/
```

The user reported completing the rsync transfer on 2026-10-01. Do not repeat the initial bulk transfer as an outstanding task. The exact command, destination inventory, and torrent hash checks have not been independently verified; exporting torrent metadata, checking payloads, importing the library, and starting local seeding remain separate steps.

For any later incremental transfer, the source trailing slash copies its contents into the destination. No `--delete`, `--inplace`, or remote owner/group preservation: retain local ACL behavior and avoid changing bytes through existing hardlinks. Runs may be previewed with `--dry-run`. This is a one-way archive pull, not a deletion mirror or bidirectional sync.

Use the torrent client to identify completed releases. If the source tree includes active downloads, the broad command can copy incomplete data; use a reviewed completed-release list or quiesce those writes before the final transfer. Do not import partial files. Schedule future pulls only if Whatbox remains a downloader, and then handle completion, locking, retries, and bounded logs explicitly.

Export original `.torrent` metadata and record torrent infohashes, save paths, and relevant client settings. Protect tracker passkeys in exported metadata as credentials. Keep Whatbox available until local verification succeeds.

### Existing-media import constraints — immediate focus

- Set Sonarr and Radarr library roots to `/data/media/tv` and `/data/media/movies`. Plex scans these roots, not the raw torrent tree.
- Add the correct series/movies initially unmonitored, with no automatic searches or upgrades.
- Treat raw release folders as downloaded material. Use interactive/manual import with copy/hardlink mode and hardlinks enabled. Existing-library import is appropriate only for already organized libraries.
- Pilot a few movies and two series, including a messy season pack. Review identity, episode mapping, specials/anime numbering, multi-episode files, quality, and duplicate editions.
- Verify normalized library naming, Sonarr/Radarr matching, and identical source/destination inode and device identifiers. Confirm the torrent source paths and bytes remain unchanged. Plex matching is a later playback-stage check, not a dependency of this milestone.
- Retain enough release quality information for later import decisions. File naming cannot resolve every ambiguous release without review.
- RAR-packed torrents need extraction into separate space; archived bytes cannot be hardlinked into an extracted video. Keep archives needed for seeding.
- Hardlinks share file contents: renaming/unlinking one path is independent, but in-place metadata edits change every link. Prevent media tools from modifying seeded payload bytes.
- Import books as copies into Calibre; use copies for comic tagging/conversion that rewrites archives. Comic organization can use hardlinks only while contents remain unchanged.
- Process the remaining library in reviewed batches. Enable monitoring/upgrades selectively after confirming the existing collection is represented correctly.

### Move seeding home — deferred; preserve payloads now

- Add each original torrent paused to the local client and select its correct save path under `/data/torrents`.
- Force recheck and require 100% completion before enabling local seeding. Resolve path mismatches and missing bytes rather than redownloading blindly.
- For migration, stop the Whatbox instance of the torrent, then start the local one. Check private-tracker client/IP requirements and connectivity, and preserve relevant seeding obligations.
- Configure incoming peer connectivity according to the actual router/ISP setup. Decide direct home-IP operation versus any VPN routing explicitly; the user wants the option to seed from home.
- Validate a small pilot before transferring the full torrent roster. Do not remove the remote copy or cancel Whatbox until the local archive, library, and seeding behavior are verified.

### Immich and other library services — deferred

- Create the separate photo dataset and access policy. Decide how existing photos enter Immich: managed uploads versus read-only external libraries. Do not point it at the torrent tree.
- Keep PostgreSQL local. Establish database plus asset backups and perform a restore test before treating phone uploads as protected storage.
- Confirm thumbnails, playback, uploads, smart search, facial recognition, OpenVINO activity, and video transcoding with a small collection first.
- Run bulk ingestion with bounded concurrency while testing Plex playback under contention. All GPU consumers share the A380 and all services share VM memory/I/O.
- Verify Calibre's import/metadata workflow and chosen device/browser access. Verify Komga reading and organization on representative comic formats. Automated comic acquisition and dedicated music/audiobook services are not yet selected.

## Retention, capacity, and recovery

Every new daemon requires an explicit log-destination audit: journal, app files, container logs, and per-job/transcode logs. Declare and verify journal caps, file rotation/reopen behavior, container rotation where relevant, and cleanup timers. Document age-based limits separately from strict byte limits. Keep log cleanup separate from media, application data, and Nix garbage collection.

Bound scratch use and alert on low guest/NAS/Proxmox storage. Verify thin-pool free space, snapshots, discard, and local metadata growth. The 200 GiB guest disk is a starting allocation, not an unlimited thumbnail/cache budget.

Back up app databases/configuration, torrent metadata, Calibre's live library, and personal photos. Define retention and a separate failure-domain copy for irreplaceable photos; snapshots alone are not that copy. Coordinate Immich database and asset recovery. Preserve seeded files during library cleanup, and understand that data remains allocated until every hardlink and retaining snapshot is gone.

Deployment checks: evaluate/build the media flake, inspect generated service/mount/retention settings, stage new Nix files for flake visibility, then apply and validate representative workflows. Do not commit automatically. Reboot Media and test NAS unavailability/recovery before declaring the system complete.

## Next action and completion criteria

Next: inspect the actual synced movie/TV inventory and current mount, bootstrap Sonarr/Radarr with acquisition disabled, and execute the reviewed matching and hardlink pilot described above. This plan update does not deploy services or start imports.

The immediate milestone passes when the pilot movies and TV episodes have correct canonical identities and episode mappings, predictable library paths, verified hardlinks, unchanged original payloads, and repeatable rescan/import behavior. The follow-on milestone is batch import of the existing movie/TV collection, with all exceptions explicitly accounted for. Neither requires Plex, GPU work, new downloads, or active seeding.

Later, validate Plex playback/hardware transcoding and local torrent rechecks. A separate photo pilot must demonstrate working Immich GPU jobs and restorable assets/database before bulk photo migration.

Finish when the collection is transferred and reviewed, desired torrents seed locally, both acquisition protocols work, books/comics are usable, photos are protected and searchable, mounts survive restarts safely, and capacity/log/backup policies are verified. Record remaining manual match exceptions explicitly.

## References

- [Whatbox rsync](https://whatbox.ca/wiki/rsync)
- [Sonarr import guidance](https://github.com/Servarr/Wiki/blob/master/sonarr/quick-start-guide.md)
- [Radarr settings and hardlinks](https://wiki.servarr.com/radarr/settings)
- [Prowlarr setup](https://wiki.servarr.com/en/prowlarr/quick-start-guide)
- [TrueNAS NFS](https://www.truenas.com/docs/scale/25.04/scaletutorials/shares/addingnfsshares/)
- [Proxmox PCI passthrough](https://github.com/proxmox/pve-docs/blob/master/qm-pci-passthrough.adoc)
- [Plex hardware acceleration](https://support.plex.tv/articles/115002178853-using-hardware-accelerated-streaming/)
- [Immich requirements](https://docs.immich.app/install/requirements/)
- [Immich hardware transcoding](https://docs.immich.app/features/hardware-transcoding/)
- [Immich OpenVINO/ML acceleration](https://docs.immich.app/features/ml-hardware-acceleration/)
- [Calibre library considerations](https://manual.calibre-ebook.com/faq.html)
- [Komga](https://komga.org/docs/introduction/)

`media-import status` reads a consistent, read-only SQLite snapshot without import
locks, so record counts remain available during background work or review. It
shows committed progress as of the start of the command.

Review preparation uses 16 parallel workers by default (`--prep-workers 1–64` on
`run` and `propose`). Identical metadata lookups share one request, with at most
four distinct API lookups in flight. Progress reports saved files, percentage,
worker count, and elapsed time. Only the main thread writes SQLite, checkpointing
each completed proposal. Cached probes and lookups are reused.

TV preparation checks that each approved episode has exactly one Sonarr record.
If initial series refreshes produce duplicates, it refreshes once to reconcile
them; persistent ambiguity stops before creating the library hardlink.
Late duplicate episode rows detected during verification also trigger one refresh
and rescan. Verification still requires the exact approved season/episode set and
destination path; only Sonarr internal row IDs may be reconciled.

TV group previews require the same parsed source title as well as the same series
and season. Merely sharing a search candidate cannot pull a different show into
the selection. Without parsed titles, grouping is limited to a shared source folder.

Explicit filename SxxEyy tokens take precedence over incidental numbers in episode
titles (for example, Ted Lasso S03E03 “4-5-1”). Contiguous multi-episode tokens are
preserved; range syntax continues through the existing parser.

Audit backups retain the latest three local snapshots and two nightly NAS snapshots.
Routine requests reuse a completed local snapshot younger than five minutes; the
explicit/nightly backup command forces a fresh snapshot. Publication is atomic,
interrupted staging files are cleaned on the next request, and pruning follows a
successful snapshot. Messages announce writing, reuse, completion size/time, NAS
copying, and removal. This is a count bound, not a byte quota: storage scales with
the live database size, with one extra snapshot temporarily during backup.
