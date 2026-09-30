# Nix build server

Status: deployed at `builder.vm.netcat.cloud` (`192.168.1.204`). The goal is a useful shared builder/cache that fits its approximately 100 GiB guest disk. Proxmox administration, physical pool monitoring, and guaranteed cache retention are outside this setup's scope.

## Configuration

- Guest: 8 vCPUs, approximately 16 GiB RAM, 99 GiB root filesystem.
- `hosts/builder/builder.nix`: restricted `remotebuild` SSH account, two jobs with four cores each, and two sandbox build users to limit concurrent ordinary builds across clients. KVM/NixOS-test features are not advertised.
- `hosts/builder/cache.nix`: signed `nix-serve` on loopback behind nginx. HTTP port 80 is allowed from the inventory LAN subnet. No web UI or Caddy alias is needed.
- `hosts/common/nix-build-client`: regular VMs inherit remote builds and the cache, retaining one local build slot and public caches. Builder and the base template are excluded. An inventory-derived host entry avoids Pi-hole's HTTP resolver bypassing split DNS and reaching the public parking page.
- Caddy and Pi-hole are enrolled and authorized. The builder's Caddy SSH host key was verified by the user and declared in Nix.

## Disk policy

Use standard Nix garbage collection, not a custom cache-retention service:

- Weekly GC removes unreferenced store paths and non-current profile generations older than 14 days. Current configurations remain protected by their GC roots.
- During builds, Nix attempts GC below 10 GiB free, aiming to restore 20 GiB free. Referenced paths cannot be collected, so these thresholds are not a hard quota or a guarantee against filling the disk.
- There is no minimum cache lifetime. An unused cached output may disappear at the next GC; clients can rebuild it. Downloading from the cache does not retain it.
- fstrim is enabled inside the guest. Physical Proxmox storage reclamation is an operator concern.

Log retention is separate and declared in `hosts/builder/logging.nix`:

- Persistent journal: up to 1 GiB/30 days, with a 5 GiB free-space target. Runtime journal: up to 128 MiB.
- nginx: daily rotation, 14 compressed archives, 50 MiB size trigger checked hourly.
- Nix build logs: daily cleanup after 30 days without modification, skipping open files. This is age-based retention, not a hard quota.

The abandoned timestamped package roots, post-build hook, migration, and custom GC/storage timers were removed in favor of this simpler policy.

## Client enrollment

New VMs: run `bin/bootstrap-nixos-vm` without arguments to get the hostname prompt. Before generating host files or building, bootstrap generates/reuses `/root/.ssh/builder`, commits and publishes **only its public key**, and checks the builder using its pinned host key. If authorization is missing:

1. Pull on the builder and run `./bin/switch`.
2. Rerun bootstrap with the same hostname. It reuses the key and continues.

Existing VMs: run `bin/bootstrap-nixos-vm --enroll-builder`, update the builder as above, rerun enrollment to verify access, then run `./bin/switch` on the client. The existing host configuration is preserved.

Private client keys never leave their owning VM. Enrollment's public-key commit/push is the explicitly authorized exception to the repository's manual-commit workflow. It rejects unrelated unpublished changes and key collisions. Other generated host/network changes remain for manual review and commit.

`--local-build` skips enrollment and disables the generated client configuration. Pair it with `--skip-update` for offline bootstrap. The base-image smoke test uses these flags so it does not depend on the LAN builder.

## Signing-key backup

The private cache signing key is `/var/lib/nix-cache/cache-key.sec`, root-owned with mode `0600`, supplied to nix-serve through systemd credentials. The public verification key is checked into the client module.

The user confirmed a backup in 1Password item `7fp7usvafbjgwnuzatnio4zyfm` on 2026-09-30. For recovery, restore the saved key to that path with root ownership and mode `0600` before starting the cache. A backup restore drill has not been performed. Do not paste the private key into Git or chat.

## Verification

- Builder, Caddy, and Pi-hole system configurations built successfully. The simplified builder configuration was applied successfully, and all 55 repository Python tests passed.
- Standard `nix-gc.service` completed successfully: 797 unreferenced paths removed, 2.0 GiB freed, leaving approximately 87 GiB free (9% used). The weekly timer is enabled; no custom package-retention services or hooks remain.
- Bootstrap tests passed, including two-run enrollment and existing-VM enrollment. Log-retention tests and an actual open-file preservation test passed.
- Caddy built a unique derivation through `ssh-ng` with local builds disabled. Pi-hole then downloaded the identical signed output over HTTP with all builders disabled. Verified output: `/nix/store/mlzq5s0pizly2x1xbrhb6wx67ggyszkc-builder-cross-vm-1790798506`.
- The real two-client test exposed Pi-hole's DNS issue; the declarative host mapping fixed it and the test passed afterward.
- A bounded two-client CPU/memory test initially ran four builds despite `max-jobs = 2`, using about 1.1 GiB for probe processes with at least 13.7 GiB available. After limiting the shared sandbox build users to two, the repeated test peaked at exactly two active builds (545 MiB combined probe RSS), and both clients completed successfully in 56 seconds.
- Cache signatures, SSH host-key checking, log rotation, and scheduled log cleanup were verified.

## Recovery

To rebuild a client without the builder/cache:

```bash
./bin/switch --builders '' --option extra-substituters '' --option substituters https://cache.nixos.org --max-jobs 1 --cores 1
```

An unavailable-server timing test and a brand-new VM bootstrap against the live builder have not been completed. These do not require additional infrastructure.
