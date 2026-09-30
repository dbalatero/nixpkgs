# Nix build server setup plan

Create a headless NixOS VM on Proxmox that builds packages for the Linux VMs and serves the results through a signed binary cache. This centralizes compilation and lets machines reuse identical builds. Each client still stores its installed runtime dependencies locally.

Status: builder deployed on 2026-09-30. SSH builds and the signed LAN cache have been verified on the server. Shared VM client configuration and bootstrap enrollment are implemented; enrollment and deployment on the other VMs remain to be done. Resource sizes below are the original proposal; actual guest resources and verification follow.

## Deployed configuration and enrollment

- `builder.vm.netcat.cloud` resolves to `192.168.1.204`. This guest has 8 vCPUs, approximately 16 GiB RAM, and a 99 GiB root filesystem (about 87 GiB available before deployment). Discard is advertised by the virtual disk. Proxmox VM ID, scheduling weight, physical storage capacity, and actual discard reclamation have not been checked.
- `hosts/builder/builder.nix` provides `remotebuild`, restricted SSH access to `nix-daemon --stdio`, two jobs and four cores, and no advertised KVM/NixOS-test support. Public keys are loaded from `hosts/builder/client-keys/*.pub`. This account is a trusted Nix user; its clients must be trusted accordingly.
- `hosts/builder/cache.nix` starts `nix-serve` on loopback behind nginx. Port 80 is allowed only from the inventory LAN subnet. There is no Caddy alias or web dashboard.
- A declared one-shot service generates `/var/lib/nix-cache/cache-key.sec` and `cache-key.pub` on the server. The private key is root-owned, mode `0600`, and passed to nix-serve through systemd credentials. Backing up this key remains an operator task. The public signing key and locally verified SSH host key are checked into `hosts/common/nix-build-client/`.
- The shared `hosts/common/nixos-vm` module enables the client for all regular VMs, including `caddy` and `pihole-dns`. It excludes `builder`, `nixos-base`, and `proxmox-base`. The builder has no remote builders and no self-cache substituter. Clients keep one local job and existing public caches. Override `lab.nixBuildClient.enable = false` for a standalone VM.
- Automatic GC remains disabled. Retention roots and expiry have **not** been implemented; monitor free space until that work is complete. fstrim is enabled, but physical storage reclamation is not yet verified.

### New VM: two-run bootstrap

Run `bin/bootstrap-nixos-vm` as usual; zero arguments prompts for the intended hostname. Before generating host files, reserving an IP, or starting a build, it:

1. Requires a clean checkout and generates or reuses `/root/.ssh/builder`. Only its public half is copied into the repository.
2. Commits only `hosts/builder/client-keys/<requested-hostname>.pub`, pulls with rebase, and pushes to the configured upstream branch. This public-key enrollment is the explicitly authorized exception to the normal manual-commit workflow. Unrelated unpublished commits and different existing keys cause a stop; conflicts require manual resolution. Git credentials, author identity, and an upstream must already be configured.
3. Checks the actual `ssh-ng` service as `remotebuild` with that identity and the pinned host key. If unauthorized, it exits and instructs you to pull and run `./bin/switch` on the builder. DNS, host-key, and service failures get separate troubleshooting guidance.
4. Run bootstrap again with the same hostname after updating the builder. It reuses the identity and public-key commit, then generates the VM configuration and builds with the remote builder supplied explicitly for this first switch. Ordinary generated host/network changes remain staged for manual review and commit.

`--local-build` skips enrollment and disables the client in the generated configuration. Bootstrapping `builder` itself also skips enrollment. `--skip-update` does not disable enrollment's Git synchronization; pair it with `--local-build` for offline operation. `--no-switch` still performs enrollment before generating files.

### Existing VM

After reviewing and publishing these implementation changes, update the checkout on each existing VM and run:

```bash
bin/bootstrap-nixos-vm --enroll-builder
```

This uses the current hostname (or an explicitly supplied hostname), generates/publishes only the key, and leaves the existing host configuration intact. After enrolling one or more VMs, pull on the builder and run `./bin/switch`. Rerun enrollment on each VM to verify access, then run `./bin/switch` there to activate the inherited client settings. No real client keys have been enrolled by this implementation session.

### Verification on 2026-09-30

- `python3 -m unittest discover -s tests`: all 50 tests passed (29 bootstrap tests), including prompted names, key collision refusal, unrelated-commit protection, idempotent publication, two-run bootstrap, existing-VM enrollment, and error classification. Git tests use local fixture repositories, never the real upstream.
- `nix build .#nixosConfigurations.builder.config.system.build.toplevel .#nixosConfigurations.caddy.config.system.build.toplevel .#nixosConfigurations.pihole-dns.config.system.build.toplevel --no-link`: passed. Existing home-manager overlay warnings remain unrelated to this change.
- Evaluation confirms `caddy` and `pihole-dns` use the builder with one local job; `builder` and `proxmox-base` have no build machines.
- `./bin/switch` successfully started `nginx`, `nix-serve`, and the signing-key provisioning service. The private key's mode and ownership were verified.
- HTTP `/nix-cache-info` and a system path's signed `.narinfo` passed. `nix store verify --store http://builder.vm.netcat.cloud --sigs-needed 1` with the checked-in public key verified content and signature.
- A temporary **declarative** test authorization authenticated over pinned `ssh-ng` (Nix 2.34.8, trusted connection), built `/nix/store/0sra0c18b5hwz079xn83jrr740bjp5r3-builder-protocol-smoke-20260930`, and copied that result from HTTP into a fresh separate local store with signature checking. The test private key and authorization were removed, and the final configuration restored. This verifies the protocol and cache without claiming a second physical VM was enrolled.
- Still pending: real client deployment, first-bootstrap distributed scheduling on a separate VM, two-client concurrency/memory tests, unavailable-server fallback timing, retention/GC tests, secret backup, and Proxmox resource verification. The checklist below remains the full rollout plan; only checked items are complete.

## Proposed resources

| Setting | Starting value |
| --- | --- |
| Hostname | `builder` |
| Architecture | `x86_64-linux` |
| CPU | 1 socket, 8 vCPUs |
| CPU scheduling | Lower CPU units than interactive/service VMs; initially half their weight |
| RAM | 16 GiB, budgeted against available host memory |
| Disk | 200 GiB on SSD/NVMe storage supporting thin provisioning |
| Network | Existing LAN bridge with VirtIO NIC |
| Guest integration | QEMU guest agent enabled |
| Initial compilation target | Two simultaneous builds, four cores per build |

CPU time is shared on demand; assigning eight vCPUs does not reserve eight physical cores. Lower CPU units give this VM less preference during contention, while a CPU limit supplies a hard ceiling if later needed. Thin storage grows with writes; discards can release unused blocks, subject to backend and snapshot behavior. [Proxmox VM documentation](https://github.com/proxmox/pve-docs/blob/master/qm.adoc).

If the host is short on memory, start with 4 vCPUs, 8 GiB RAM, 100 GiB disk, and one build at a time. Increase RAM before concurrency if builds encounter memory pressure. Do not depend on ballooning to make an overcommitted host safe.

## 1 Inspect the host and create the VM

- [ ] Check physical CPU count, available RAM, storage pool capacity, and the other VMs' normal workloads. Record the selected Proxmox node, VM ID, bridge, storage backend, and resource allocation here.
- [ ] Follow [the existing base image plan](proxmox-nixos-base-image.md) and repository README to clone the prepared NixOS template. Preserve its working firmware and boot configuration.
- [ ] Set the proposed resources. Use compatible VirtIO storage, enable discard where the backend supports it, and resize the clone's disk before its first boot. Leave the template unchanged.
- [ ] Boot the clone and verify `lsblk`, `df -h /`, guest agent operation, and console access. Confirm the root partition and filesystem grew to the new size.

## 2 Bootstrap and register the host

Use the canonical repository checkout inside the guest. Start with a current, clean checkout; preserve any local changes instead of resetting them. The existing bootstrap command generates hardware configuration, a host module, a home-manager host, a flake entry, and an inventory entry.

- [ ] Run `bin/bootstrap-nixos-vm --suggest-ip` to inspect the next inventory candidate. Check the candidate is actually unused on the LAN; the inventory is not a network scan.
- [ ] From the Proxmox console, run the following after reviewing the candidate. `--no-switch` generates and stages files for review before changing networking.

```bash
bin/bootstrap-nixos-vm builder \
  --description "Shared Nix builder and binary cache" \
  --static-ip auto \
  --no-switch
```

- [ ] Review `hosts/builder/`, `home/hosts/builder/`, `flake.nix`, and `lab/network.json`. Use the current inventory's gateway and DNS defaults. Do not hardcode an IP from this plan.
- [ ] Apply with `./bin/switch` in the guest. Networking may change; retain console access.
- [ ] Transfer the reviewed changes through the user's normal Git workflow. Do not create commits or push automatically. Deploy the updated inventory on `pihole-dns` with `./bin/switch` so it generates `builder.vm.netcat.cloud`.
- [ ] Verify that name resolves to the new VM from each pilot client. Use the direct machine name for SSH and caching; this initial setup needs no Caddy alias or public DNS.

## 3 Configure the build service in NixOS

Put server configuration in `hosts/builder/builder.nix` and import it from the generated `configuration.nix`. Preserve the generated hardware and user configuration. All persistent service and Nix settings belong in Nix modules.

- [x] Create a dedicated `remotebuild` account and group, using public keys for authentication. Keep root SSH login disabled as in the shared VM module.
- [ ] Provision a distinct SSH private key for each client daemon at `/root/.ssh/builder`, mode `0600`. Generate secrets on the owning machines; never put private keys in Git, chat, or the Nix store. Declare their public keys on the builder through Nix.
- [x] Configure the build account's Nix daemon access following the remote builder guide. A Nix trusted user is highly privileged; give this access only to the intended build clients.
- [ ] Declare and verify the builder's SSH host key in each client's `programs.ssh.knownHosts`; do not disable host-key checking.
- [ ] Start with builder `nix.settings.max-jobs = 2` and `nix.settings.cores = 4`. Measure actual behavior with multiple clients: each client's advertised remote `maxJobs` is not a fleet-wide concurrency limit. Verify how the chosen SSH protocol and Nix version apply server limits before increasing concurrent submissions.
- [x] Keep `cache.nixos.org` available to the builder. Do not configure it to build through itself or substitute from its own HTTP cache.
- [x] Advertise only verified system features. Add `kvm` and `nixos-test` only after nested virtualization and an actual NixOS VM test work inside the guest.

The authentication and distributed build workflow is described in the [Nix remote builder guide](https://nix.dev/tutorials/nixos/distributed-builds-setup.html). This Linux builder initially serves x86_64 Linux builds; Darwin builds need a suitable Darwin builder.

## 4 Serve a signed binary cache

Put cache configuration in `hosts/builder/cache.nix` and import it from the host module.

- [ ] Generate a cache signing key pair on the server. Store the private key outside the repository and Nix store, with permissions allowing only the required service access. Back it up securely; record the public key in the client module.
- [x] Enable `services.nix-serve`, pointing `secretKeyFile` at the provisioned private key. Bind the backend to loopback and put nginx on port 80 in front of it.
- [x] Serve `http://builder.vm.netcat.cloud` on the LAN. Allow the cache port from the intended LAN subnet in the declared firewall rules; do not add WAN port forwarding.
- [x] Verify `/nix-cache-info` responds and a known store path's `.narinfo` has a signature. Signed packages provide authenticity over this initial LAN HTTP endpoint; HTTP does not provide confidentiality.
- [x] Add the server URL to clients' `extra-substituters` and its public key to `extra-trusted-public-keys`, preserving existing public caches and keys.

This follows the [Nix binary cache guide](https://nix.dev/tutorials/nixos/binary-cache-setup.html). The cache serves objects already in the builder's store; it is not automatically a pull-through mirror of every package downloaded by clients.

## 5 Enable the shared VM client module

Implemented in `hosts/common/nix-build-client/default.nix`. Per the requested rollout, `common/nixos-vm` enables it by default for regular VMs and excludes the builder and base template. Stage new Nix files so the flake sees them. Evaluate options against the repository's pinned Nixpkgs before deployment.

- [x] Set `nix.distributedBuilds = true` and `nix.settings.builders-use-substitutes = true`.
- [x] Declare `nix.buildMachines` with host `builder.vm.netcat.cloud`, protocol `ssh-ng`, user `remotebuild`, key `/root/.ssh/builder`, system `x86_64-linux`, and initial `maxJobs = 2`.
- [x] Include the host-key declaration, cache URL, and public signing key from the previous steps.
- [x] Keep a small positive local `max-jobs`, initially 1, so local builds remain possible. Distributed builds permit local execution too; this is not a guarantee that every derivation goes remotely.
- [x] Keep build dependencies on the builder where possible via `builders-use-substitutes`. Evaluation and some derivation preparation still happen on clients.
- [ ] Apply on the pilot with `./bin/switch`, then expand to other Linux VMs after the checks below. Keep the client disabled on the builder and base template.

## 6 Validate building and reuse

- [ ] Evaluate and build the builder's NixOS configuration and the pilot client's configuration before switching. Run `git diff --check`. Record commands and outcomes.
- [ ] Verify the client's root-owned SSH identity can contact the build service without an interactive prompt.
- [ ] Use a small unique test derivation absent from all caches. Build on the pilot with `--max-jobs 0` for this test only, and confirm logs show remote execution and copying the result back.
- [ ] Request the identical derivation on a second client with no existing output. Disable remote builders for that test and verify it substitutes from the LAN cache with signature checking enabled. This distinguishes cache reuse from another remote build.
- [ ] Rebuild a real client configuration and inspect CPU, RAM, build duration, and disk usage on both machines. Keep the same flake lock when comparing shared results.
- [ ] Test two clients submitting builds together. Record peak memory and the number of active jobs; lower per-client concurrency if the builder is overcommitted.
- [ ] Test an unavailable builder/cache and document observed delays and fallback. Keep an explicit recovery invocation: `./bin/switch --builders '' --option extra-substituters '' --option substituters https://cache.nixos.org --max-jobs 1 --cores 1`. Verify it with the actual client configuration; do not assume transparent fallback is instant.

## 7 Manage disk growth and retention

Garbage collection removes unreachable store paths. Old system generations and other roots retain their dependencies; merely serving a cache does not keep packages rooted. A generation age policy is not a minimum retention time for arbitrary remote build outputs. [Nix garbage collection](https://nix.dev/manual/nix/2.35/package-management/garbage-collection.html).

- [ ] Implement and test a server retention mechanism before enabling automatic GC. Proposed policy: a declared post-build hook records output GC roots with timestamps; a declared timer expires these roots after 30 days, then runs GC. Rebuilding/reusing an output must have documented renewal behavior. This is extra implementation work, not a built-in property of `nix-serve`.
- [ ] Keep the builder's current system and desired rollback generations. On clients, propose weekly GC and removal of generations older than 14 days, preserving current configurations. Review existing host policies before changing them.
- [ ] Declare `services.fstrim.enable = true` where supported, then verify deleted guest data can be reclaimed by the Proxmox backend. Snapshots can retain blocks after guest deletion.
- [ ] Monitor both guest free space and the physical thin pool, including metadata if using LVM-thin. Start investigating at 80% usage; guest free space alone does not prove host capacity is available.
- [ ] Back up signing keys and required access secrets. Treat cached packages as rebuildable data; avoid retaining large VM snapshots indefinitely just to preserve cache contents.

## Completion criteria

- [ ] A normal rebuild from a client can use the remote builder.
- [ ] A second client reuses a signed result over HTTP without rebuilding it.
- [ ] Busy builds leave other services responsive and fit within available host RAM.
- [ ] Garbage collection preserves retained outputs and removes expired, unreferenced ones.
- [ ] The local recovery command works when the builder is unavailable.
- [ ] Record the actual VM ID, resources, address, key locations, enabled clients, verification results, and remaining issues in this plan. Leave Git review and commits to the user.
