# Nix build server setup plan

Create a headless NixOS VM on Proxmox that builds packages for the Linux VMs and serves the results through a signed binary cache. This centralizes compilation and lets machines reuse identical builds. Each client still stores its installed runtime dependencies locally.

Status: planning only. No VM, keys, services, or client configuration have been created by this plan. Resource sizes below are starting recommendations; check host capacity before provisioning. Keep implementation progress and runtime evidence here as work proceeds.

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

- [ ] Create a dedicated `remotebuild` account and group, using public keys for authentication. Keep root SSH login disabled as in the shared VM module.
- [ ] Provision a distinct SSH private key for each client daemon at `/root/.ssh/builder`, mode `0600`. Generate secrets on the owning machines; never put private keys in Git, chat, or the Nix store. Declare their public keys on the builder through Nix.
- [ ] Configure the build account's Nix daemon access following the remote builder guide. A Nix trusted user is highly privileged; give this access only to the intended build clients.
- [ ] Declare and verify the builder's SSH host key in each client's `programs.ssh.knownHosts`; do not disable host-key checking.
- [ ] Start with builder `nix.settings.max-jobs = 2` and `nix.settings.cores = 4`. Measure actual behavior with multiple clients: each client's advertised remote `maxJobs` is not a fleet-wide concurrency limit. Verify how the chosen SSH protocol and Nix version apply server limits before increasing concurrent submissions.
- [ ] Keep `cache.nixos.org` available to the builder. Do not configure it to build through itself or substitute from its own HTTP cache.
- [ ] Advertise only verified system features. Add `kvm` and `nixos-test` only after nested virtualization and an actual NixOS VM test work inside the guest.

The authentication and distributed build workflow is described in the [Nix remote builder guide](https://nix.dev/tutorials/nixos/distributed-builds-setup.html). This Linux builder initially serves x86_64 Linux builds; Darwin builds need a suitable Darwin builder.

## 4 Serve a signed binary cache

Put cache configuration in `hosts/builder/cache.nix` and import it from the host module.

- [ ] Generate a cache signing key pair on the server. Store the private key outside the repository and Nix store, with permissions allowing only the required service access. Back it up securely; record the public key in the client module.
- [ ] Enable `services.nix-serve`, pointing `secretKeyFile` at the provisioned private key. Bind the backend to loopback and put nginx on port 80 in front of it.
- [ ] Serve `http://builder.vm.netcat.cloud` on the LAN. Allow the cache port from the intended LAN subnet in the declared firewall rules; do not add WAN port forwarding.
- [ ] Verify `/nix-cache-info` responds and a known store path's `.narinfo` has a signature. Signed packages provide authenticity over this initial LAN HTTP endpoint; HTTP does not provide confidentiality.
- [ ] Add the server URL to clients' `extra-substituters` and its public key to `extra-trusted-public-keys`, preserving existing public caches and keys.

This follows the [Nix binary cache guide](https://nix.dev/tutorials/nixos/binary-cache-setup.html). The cache serves objects already in the builder's store; it is not automatically a pull-through mirror of every package downloaded by clients.

## 5 Add an opt in client module

Create `hosts/common/nix-build-client/default.nix` and initially import it from one noncritical NixOS VM. Stage new Nix files so the flake sees them. Evaluate options against the repository's pinned Nixpkgs before deployment.

- [ ] Set `nix.distributedBuilds = true` and `nix.settings.builders-use-substitutes = true`.
- [ ] Declare `nix.buildMachines` with host `builder.vm.netcat.cloud`, protocol `ssh-ng`, user `remotebuild`, key `/root/.ssh/builder`, system `x86_64-linux`, and initial `maxJobs = 2`.
- [ ] Include the host-key declaration, cache URL, and public signing key from the previous steps.
- [ ] Keep a small positive local `max-jobs`, initially 1, so local builds remain possible. Distributed builds permit local execution too; this is not a guarantee that every derivation goes remotely.
- [ ] Keep build dependencies on the builder where possible via `builders-use-substitutes`. Evaluation and some derivation preparation still happen on clients.
- [ ] Apply on the pilot with `./bin/switch`, then expand to other Linux VMs after the checks below. Do not import the client module into the builder or base template globally.

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
