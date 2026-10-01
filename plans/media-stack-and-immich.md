# Media stack, Whatbox migration, and Immich

Status: infrastructure partly complete; application deployment and migration pending. Updated 2026-10-01. This plan records the conversation, repository configuration, and read-only Proxmox MCP inspection. It does not authorize deploying the remaining services automatically.

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

## Implementation sequence

### 1. Storage access and mount lifecycle

- Configure a TrueNAS NFS export for `warez/data` to the intended clients. Use normal numeric UID/GID access, preserve individual identities, leave Mapall unset, and retain root squashing.
- Declare the guest mount in NixOS. Start with NFSv4.1/TCP, hard mounting, and negotiated transfer sizes. Benchmark default connectivity against `nconnect=4` only if throughput warrants tuning; do not assume more connections are faster.
- Both VMs already use VirtIO on vmbr0. Traffic stays within the host when they share bridge/VLAN/subnet; physical LAN speed still matters for desktop clients.
- Make dependent services require the mount and verify its presence before writing. An absent NAS must not cause applications to populate the VM's underlying empty `/data` directory. Test outage/recovery and startup behavior.
- Check group 2000 in guests and containers, ACL inheritance, actual service write access, and a hardlink from a temporary torrent file to a temporary library path. Plex should receive read access to media; only necessary writers join `media`.
- Optional SMB access is a later share configuration, not enabled merely by marking the group as SMB-capable. Recheck permission behavior if configuring multiprotocol access.

### 2. Intel userspace drivers and GPU validation

- Inspect the pinned nixpkgs/NixOS options and configure Intel Arc media and compute userspace support declaratively. Kernel passthrough is already complete.
- Validate supported video profiles with appropriate tools, then test a representative hardware transcode. Verify hardware activity rather than relying only on device visibility.
- Configure Plex hardware acceleration and confirm Plex Pass availability. Test actual playback, including desired HDR-to-SDR behavior and subtitle cases, which can still involve CPU work.
- Configure Immich video acceleration through QSV/VAAPI and ML acceleration through OpenVINO independently. Confirm actual inference uses the GPU, rather than silently falling back to CPU.
- Start with modest background-job concurrency. Test simultaneous Plex playback and Immich processing before increasing it.

### 3. Deploy the application stack

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

### 4. Copy the Whatbox collection

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

Transfer completion is unverified. The source trailing slash copies its contents into the destination. No `--delete`, `--inplace`, or remote owner/group preservation: retain local ACL behavior and avoid changing bytes through existing hardlinks. Initial runs may be previewed with `--dry-run`. This is a one-way archive pull, not a deletion mirror or bidirectional sync.

Use the torrent client to identify completed releases. If the source tree includes active downloads, the broad command can copy incomplete data; use a reviewed completed-release list or quiesce those writes before the final transfer. Do not import partial files. Schedule future pulls only if Whatbox remains a downloader, and then handle completion, locking, retries, and bounded logs explicitly.

Export original `.torrent` metadata and record torrent infohashes, save paths, and relevant client settings. Protect tracker passkeys in exported metadata as credentials. Keep Whatbox available until local verification succeeds.

### 5. Import an organized library without disturbing seeding

- Set Sonarr and Radarr library roots to `/data/media/tv` and `/data/media/movies`. Plex scans these roots, not the raw torrent tree.
- Add the correct series/movies initially unmonitored, with no automatic searches or upgrades.
- Treat raw release folders as downloaded material. Use interactive/manual import with copy/hardlink mode and hardlinks enabled. Existing-library import is appropriate only for already organized libraries.
- Pilot a few movies and two series, including a messy season pack. Review identity, episode mapping, specials/anime numbering, multi-episode files, quality, and duplicate editions.
- Verify normalized library naming, Plex matching, and identical source/destination inode and device identifiers. Confirm the torrent source paths and bytes remain unchanged.
- Retain enough release quality information for later import decisions. File naming cannot resolve every ambiguous release without review.
- RAR-packed torrents need extraction into separate space; archived bytes cannot be hardlinked into an extracted video. Keep archives needed for seeding.
- Hardlinks share file contents: renaming/unlinking one path is independent, but in-place metadata edits change every link. Prevent media tools from modifying seeded payload bytes.
- Import books as copies into Calibre; use copies for comic tagging/conversion that rewrites archives. Comic organization can use hardlinks only while contents remain unchanged.
- Process the remaining library in reviewed batches. Enable monitoring/upgrades selectively after confirming the existing collection is represented correctly.

### 6. Move seeding home

- Add each original torrent paused to the local client and select its correct save path under `/data/torrents`.
- Force recheck and require 100% completion before enabling local seeding. Resolve path mismatches and missing bytes rather than redownloading blindly.
- For migration, stop the Whatbox instance of the torrent, then start the local one. Check private-tracker client/IP requirements and connectivity, and preserve relevant seeding obligations.
- Configure incoming peer connectivity according to the actual router/ISP setup. Decide direct home-IP operation versus any VPN routing explicitly; the user wants the option to seed from home.
- Validate a small pilot before transferring the full torrent roster. Do not remove the remote copy or cancel Whatbox until the local archive, library, and seeding behavior are verified.

### 7. Immich and library services

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

Next: inspect the pinned Intel graphics options and configure userspace acceleration in Media; in parallel with that planning, finish the NAS NFS export and declarative guest mount. Do not redo the already verified GPU passthrough.

The first end-to-end milestone is one synced TV release that remains hash-valid for local seeding, imports through hardlinks, matches correctly in Plex, and hardware-transcodes successfully. A separate photo pilot must demonstrate working Immich GPU jobs and restorable assets/database before bulk photo migration.

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
