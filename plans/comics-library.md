# Comics library and iPad reading

Status: proposed implementation; this plan does not deploy or import anything.

## Decisions

- Run Komga on the media host, exposed through Caddy at `comics.netcat.cloud`.
- Use Panels on iPad for browsing, streaming, offline downloads, and reading-progress sync.
- Keep CWA responsible for ebooks.
- Use the existing qBittorrent `comics` category; do not create a duplicate category or tag.
- Copy comics into the managed library while preserving torrent originals for seeding.
- Reuse the existing Python importer, dispatching to separate ebook and comic functions.
- Keep all service configuration and dependencies declared in Nix.

Panels server connections require Premium, available by subscription or a one-time purchase for the current major version. Download comics inside the connected server library to retain its relationship to the server. Access away from home requires connectivity to the home server, such as a VPN; already downloaded comics can be read offline.

## Storage

| Purpose | Path |
| --- | --- |
| Existing torrent source | `/mnt/warez/torrents/Comics` |
| Comic imports needing organization/review | `/mnt/warez/media/comics/incoming` |
| Organized Komga library | `/mnt/warez/media/comics/library` |
| Incomplete copies and extraction workspace | `/mnt/warez/media/comics/.staging` |
| Komga application state/database | Local storage under `/var/lib/komga` |

Start with copies: the NAS had roughly 82 TB free when checked. Revisit hardlinks or reflinks only if storage usage warrants the additional constraints. Do not make a second permanent copy between incoming and library: promotion within the same filesystem should be a rename.

Komga scans only `library`, not incoming or staging. Use one directory per series/run, containing issue or volume files. Keep distinct runs/editions separate. A torrent folder containing several unrelated series must not become one artificial series.

## One Python importer, separate media handlers

Extend `tools/ebook_import.py` initially, preserving the installed `ebook-import` command and its existing state. A neutral command alias can be added without renaming the database or forcing a migration just for naming.

Suggested function boundaries:

```python
HANDLERS = {
  'books': process_ebooks,
  'comics': process_comics,
}

def process_job(job, settings):
  torrent = fetch_completed_torrent(job.torrent_id, settings)
  handler = HANDLERS.get(torrent.category)
  if handler is None:
    return ignored_result()
  sources = validate_torrent_files(torrent, settings)
  return handler(job, sources, settings)
```

This is a sketch of the boundaries, not replacement code ready to run.

Share the following mechanisms:

- qBittorrent API access and exact selected-file-list validation.
- Completion/category checks, safe relative paths, and symlink rejection.
- Persistent queue, retries, worker locking, status reporting, and crash recovery.
- Streaming copies, content hashes, source stability checks, and duplicate prevention.
- Archive listing and streaming extraction with path, size, file-count, and nesting limits.
- Atomic publication and cleanup of the worker's own abandoned scratch files.

Keep these decisions in the format-specific handlers:

| Ebook handler | Comic handler |
| --- | --- |
| Prefer EPUB → AZW3 → MOBI → PDF per confidently matched book | Preserve CBZ, CBR, and comic PDFs; do not rank these as interchangeable editions |
| Flatten selected books into CWA's incoming directory as currently implemented | Preserve meaningful series/run directories and issue filenames |
| CWA consumes the handoff | Komga scans files promoted into the organized library |
| Existing ebook extraction limits | Separately configured limits suitable for larger comic files and packs |

The shared archive helper should accept a policy defining supported payloads, wrapper archives, and resource limits. It must stop at terminal payload files:

- `collection.zip` containing `Series/001.cbz`: extract the ZIP wrapper; keep `001.cbz` intact.
- `001.cbz` or `001.cbr`: treat as a comic, not as another wrapper to unpack.
- A plain ZIP/RAR containing page images may itself be a comic. Detect and flag this case for review initially; do not silently discard its pages or guess at conversion.
- Reuse multipart/nested archive handling where applicable, with the same safety checks.
- Do not let adding comic formats alter the ebook handler's behavior.

Avoid copying an entire large comic torrent into local scratch before processing it. Stream ordinary comic files directly into NAS staging, and stage/extract only wrapper archives that require it. Hash while copying. Check free space and enforce configured expansion limits.

## Queue and service behavior

Keep qBittorrent's single completion hook. It passes the torrent ID and category to the same script, which queues recognized categories and exits quickly. Continue using categories for dispatch, not free-form tags.

The worker rechecks the live torrent category and file list. Category changes must not publish files through a handler selected from stale queue data.

Start with the existing timer/worker model. A large comic pack can delay ebook processing; document that initial tradeoff. If that becomes noticeable, run category-filtered worker units from the same script, with safe per-job claiming and separate locks. Do not duplicate the importer just to obtain separate scheduling.

Preserve existing ebook job IDs and delivered hashes. Make schema changes additive and transactional, with a database backup before migration. Deduplication must include destination/media identity so an ebook delivery cannot suppress a comic delivery of identical bytes. Record the delivery path and whether a comic is awaiting review or published, so retries after promotion do not recreate the incoming copy.

The worker currently mounts the whole ebook root writable to keep staging-to-incoming renames on one sandbox mount. Apply the same pattern to the comic root; separate bind mounts for individual subdirectories can cause `EXDEV` even on the same underlying NAS filesystem.

## Comic organization and backlog

1. Inspect representative torrents and embedded ComicInfo metadata before defining folder rules.
2. Preview the proposed destination for every issue without writing files.
3. Publish clearly organized single-series or preserved series-subfolder imports automatically.
4. Put ambiguous multi-series packs, filename collisions, and uncertain editions into incoming with a review report.
5. Preserve filenames needed for issue ordering. Resolve collisions explicitly rather than overwriting files.
6. Support deliberate promotion of reviewed imports into the library, updating the delivery record.

Exact byte duplicates can be skipped. Different scans, languages, resolutions, and collected editions should not be discarded merely because their titles look similar.

Do not automatically ingest the existing backlog. First produce a report of comic files in both Comics and Books torrent directories; older comic torrents may be filed under Books. Backfill is a separate, explicitly selected operation after the new-completion workflow works.

## Komga, authentication, and networking

- Check the pinned nixpkgs Komga service/package before choosing native deployment versus a pinned container.
- Keep application state local; mount only the managed comic library for scanning/reading, preferably read-only.
- Match the established NAS user/group permissions and require the verified NAS mount before startup.
- Add a `comics.netcat.cloud` service entry to the shared network inventory, with the backend port restricted to Caddy.
- Configure native Authentik OIDC for browser accounts. Declare the authorization-code grant explicitly; Authentik's new-provider default previously caused the Books login loop.
- Allow an appropriate Comics users group and `authentik Admins` to access the application. Decide application-admin mapping separately from login access.
- Configure per-user Panels credentials using a method supported by the selected Komga/Panels versions. Browser OIDC login is not automatically an OPDS-client login.
- Keep OPDS/API endpoints free of an outer interactive SSO gate; rely on their own authentication.
- Hand off Pi-hole and Caddy application steps using the established workflow.

Bound every service's logs. Reuse the verified journal policy where applicable, configure rotation for any application file logs, and expire successful per-job reports. Preserve unresolved review records and durable deduplication state; log cleanup must not remove comics or torrent files.

## Implementation sequence

1. Inventory representative comics and preview organization/size requirements.
2. Refactor shared importer helpers while preserving ebook behavior.
3. Add comic dispatch, archive policy, configurable limits, and publication/review states.
4. Declare the comic directories and worker permissions in Nix.
5. Deploy Komga and create its library against the managed library path.
6. Configure DNS, Caddy, Authentik, and separate accounts.
7. Connect Panels and verify online/offline reading on the iPad.
8. Review a dry-run backlog report before selecting any historical imports.

## Acceptance checks

- Existing ebook selection, deduplication, archive, and crash-recovery tests still pass.
- Completed `books` and `comics` torrents reach their respective handlers; other categories are ignored.
- Torrent originals remain unchanged, including after metadata edits in the managed library.
- CBZ/CBR payloads remain intact; nested/split wrapper packs extract safely.
- Unsafe paths, incomplete files, missing archive volumes, excessive expansion, and disk-space failures produce actionable status.
- Retries and restarts do not duplicate published or promoted files.
- Komga does not see partial copies or review-only imports.
- Two users have separate reading progress against the same library.
- The real browser OIDC round trip succeeds, not merely the initial redirect.
- Panels browses the library, downloads a series, reads offline, and syncs progress after reconnecting.
- Log retention and service restart behavior are verified on the deployed host.

## References

- [Komga scanning and folder-to-series mapping](https://komga.org/docs/guides/scan-analysis-refresh/)
- [Komga OAuth2/OIDC](https://komga.org/docs/installation/oauth2/)
- [Panels with Komga](https://www.panels.app/komga-ios-app)
- [Panels Premium purchase options](https://guides.panels.app/premium/what-is-panels-premium)
