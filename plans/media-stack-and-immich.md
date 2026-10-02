# Media stack, Whatbox migration, and Immich

Status: initial import stack and incremental audit tooling implemented on 2026-10-01. Whatbox rsync transfer was reported complete. Library imports require saved terminal batch approvals; no existing media has been imported yet. Local seeding remains deferred. The implementation notes below supersede earlier workflow details where they differ.

## Implemented incremental audit workflow

`hosts/media/import-stack.nix` declares Sonarr, Radarr, Lidarr, Audiobookshelf, and the `media-import` CLI. All four applications bind to localhost. A Nix-managed initializer sets migration safety options via the applications' APIs, generates local login credentials, and supplies private API-key files. Application state and the audit database stay on the VM disk.

The actual mount is `/mnt/warez`, backed by `truenas.vm.netcat.cloud:/mnt/warez/data`. Keep `/mnt/warez/torrents` unchanged. Library directories are ordinary directories under `/mnt/warez/media`: `movies`, `tv`, `music`, `audiobooks`, `spoken-word`, and `alternates`.

The shared NFS module disables idle unmounting (`x-systemd.idle-timeout=0`) for both Media and Panther. The former ten-minute timeout was confirmed to stop Media's dependent applications before unmounting the share. Automounting and mount-presence checks remain enabled; an idle share stays mounted.

### Records and incremental behavior

The authoritative database is `/var/lib/media-import/audit.sqlite`, owned by `dbalatero`. It records source paths, immutable file revisions, probes, metadata lookup evidence, proposals, decisions, approved manifests, operations, and verification history. The database is not stored on NFS. Runtime credentials in this directory are secrets, not repository files.

- Inventory scans register new paths and update observations without re-probing or rehashing unchanged files. A new file must have two unchanged observations at least ten minutes apart before proposal generation. This is a stability heuristic; batch approval also requires confirming transfers are finished.
- Changed source metadata produces a new revision. Existing approval no longer applies. Files touched after an import operation began are held for investigation rather than automatically requeued.
- Missing files are recorded only after a complete successful scan. No library file is deleted. Mount mismatches, traversal errors, symlinks, and partial transfers fail closed or remain explicit exceptions.
- A verified operation is skipped on subsequent `apply` runs, including hashing and application calls. `verify` explicitly requests full content and application checks again.
- `propose` performs local ffprobe/filename analysis and queries the local Radarr, Sonarr, or Lidarr APIs. Metadata responses are cached. No per-file LLM calls are used. Audiobook proposals use existing tags and explicit author/title/order review.
- Source paths are separate records even if content is identical. Before-hash comparisons flag duplicate content among import operations; alternate imports must be explicitly selected.

### Commands, run on Media as dbalatero

```bash
media-import inventory
# After transfers finish and at least ten minutes have elapsed:
media-import inventory
media-import status

# Prepare a small, bounded first review queue:
media-import propose --kind movie --limit 10
media-import review

# Preview and approve exactly the accepted, unbatched mappings:
media-import approve --accepted
# This is separate from approval; substitute the displayed batch ID:
media-import apply 1
media-import verify 1

media-import backup
media-import export /var/lib/media-import/export
```

The terminal review offers candidate selection, full evidence, mapping edits in `$EDITOR`, explicit exclusions/deferrals, and alternate versions outside app-managed roots. TV seasons and music albums can be reviewed as a group with every source-to-destination mapping displayed before acceptance. Music requires selecting a specific MusicBrainz release. Review and approval never execute imports. Use explicit proposal IDs with `approve` to select a smaller batch instead of `--accepted`.

For focused investigation, `media-import list --kind movie --contains Brazil` finds stable file IDs and outcomes; `media-import show FILE_ID` shows their observations, proposals, decisions, and operations. CSV exports include a joined `current.csv` with one row per source path, its current outcome, destination, identity, reason, and recorded hash. `propose --files FILE_ID --kind KIND --retry` regenerates an unreviewed proposal, optionally with `--refresh-metadata`; it does not reopen decisions or completed imports. `reopen FILE_ID` explicitly edits a previously reviewed mapping while preserving history and refuses files with existing import operations. Difficult corrections after an operation began need investigation of that operation; there is deliberately no bulk reset/delete command.

Archive work stays separate: `propose --kind archive --files FILE_ID ...` records member listings without extraction. Do not approve an archive as a media file. The known movie/TV/music exceptions include five Conan RAR releases, Malcolm in the Middle season-one ZIP, Prison Break subtitle RARs, The Threepenny Opera FLAC ZIP, and a misplaced software ZIP. Other categories remain inventoried even though ebook/comic/software application management is deferred.

### Execution and verification

Implementation adjustment: the importer registers the approved identity unmonitored through supported app APIs, creates the exact approved hardlink itself using `link(2)`, and then asks the app to scan its organized library path. It never falls back to copying. Apps see the NAS read-only, preventing tag rewrites, source deletion, renames, or replacements. Lidarr tag writing is additionally disabled through the API. All app metadata/database writes stay local.

Every approved manifest has a digest and specific source revision IDs. The executor revalidates decisions, source observations, and destination collisions; backs up app state; saves a pre-import SHA-256; records progress before side effects; and checks both inode identity and the app's movie/episode/track assignment before marking an operation verified. A crash after creating a hardlink can be reconciled against the saved hash. Failed app matching leaves a recorded linked-but-unverified operation for correction, never a false success. No source move, deletion, permission rewrite, tag modification, or automatic extraction is performed.

The first real collection pilot still requires user approval. Cover a flat movie, a movie with companions, a TV season, single/multidisc music, and single/multipart audiobooks. Synthetic filesystem tests do not establish that the real collection has been correctly matched.

### Access, backups, and logs

For UI access from another machine, use SSH forwarding; do not open public ports:

```bash
ssh -N -L 7878:127.0.0.1:7878 -L 8989:127.0.0.1:8989 \
  -L 8686:127.0.0.1:8686 -L 8000:127.0.0.1:8000 dbalatero@media.vm.netcat.cloud
```

The initialized username is `dbalatero`; private generated passwords are `/var/lib/media-import/{radarr,sonarr,lidarr,audiobookshelf}.password`. Read them locally when needed; do not paste them into chat or Git. API keys are separate files. The initializer does not reset an existing Audiobookshelf account.

SQLite online backups are taken locally after review/approval and before imports. `media-import backup` copies a consistent snapshot to `/mnt/warez/media-import-audit`; a daily Nix-managed timer also does this. Keep migration history and backups through handover; these are persistent audit artifacts, not disposable logs. Backups on the same NAS are not an independent failure-domain backup.

Journald uses the existing 512 MiB persistent / 128 MiB runtime / 14-day limits. Servarr uses native rotation, explicitly configured for ten 1 MiB archives per enabled level, with info logging and its separate log database disabled. Audiobookshelf daily and scan logs older than fourteen days are removed by a timer; this is age-based, not a strict quota. Crash logs rotate daily or when checked above 10 MiB, with seven compressed rotations. Log cleanup never deletes application databases, media, or Nix packages.

Validation includes `python3 -m unittest discover -s tests/media_import -v`, Nix evaluation/build, actual service/API checks, and a temporary NAS hardlink readable by all four service identities. The initial live inventory found 16,471 files without scan errors. Actual collection import, real-match verification, and future torrent rechecks remain separate milestones.

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

- Record a source manifest and content hashes for the small pilot before import. Snapshot/backup importer state before a batch so incorrect metadata assignments can be recovered.
- Import with the explicit copy/hardlink mode, never move mode. Verify the installed app version's actual behavior; a setting named "use hardlinks" can still fall back to copying.
- Compare source and destination `stat` data from the same client mount: device and inode must match and link count must reflect the additional name. File size equality alone is insufficient. If the app copied, stop expansion and diagnose mounts, permissions, or import mode.
- Confirm source filenames, paths, and bytes match the pre-import manifest. A checksum comparison between two current hardlinks is not proof that neither was modified; compare against the pre-import hashes.
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
