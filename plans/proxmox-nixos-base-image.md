# Proxmox NixOS Base Image Plan

## Goal

Create an x86_64 Linux `qcow2` base image for Proxmox. It boots headless NixOS, has this repo cloned at `/home/dbalatero/.config/nixpkgs`, accepts the laptop and desktop SSH public keys for login, has a shared console recovery password chosen during image preparation, and contains a shared GitHub SSH write key for repo push/pull.

Implement, evaluate, build, and test on the current x86_64 Linux desktop. The unattended agent scope ends with a prepared image and local tests; the user will import it into Proxmox and perform the actual template and clone trial later. No Mac handoff is required.

**First-login success:** after cloning the template, SSH in as `dbalatero`, open the existing writable repo, run one bootstrap command to name and configure that VM, edit its NixOS configuration, rebuild locally, then commit and push to GitHub. No separate installation, manual repo clone, or hand-edited system file should be needed.

Keep `lab/README.md` as the short operator guide for creating a VM. Update it when each phase supplies a tested command or decision; keep implementation details and exhaustive checks in this plan.

## Agent execution agreement

- Work on the current x86_64 Linux desktop, delegating implementation and verification to sub-agents while the main agent orchestrates. Complete Phases 1 and 2; leave Phase 3 to the user.
- The user explicitly authorizes frequent small implementation commits, overriding the older no-automatic-commit guidance for this task. Stage new Nix files for flake evaluation, commit only task changes, preserve unrelated working-tree changes, and **never push**.
- Reuse the existing `bin/new-host` and `hosts/template` where helpful, but make the VM bootstrap safe for this image. Default to a headless profile; accept only profiles backed by real modules in this repo and reject unknown values.
- The user supplied `hosts/proxmox-base/authorized_keys` containing the approved login public keys. This public-only file may be committed. Validate its entries and fingerprints; do not guess replacement keys or request private material in chat.
- On 2026-09-26, validated both RSA login public keys in `authorized_keys` (desktop and laptop). The dedicated Ed25519 GitHub private/public pair matches, the private key is owned by `dbalatero` with mode `0600`, and it works without a passphrase. After the user registered the key on the repository, a read-only `git ls-remote git@github.com:dbalatero/nixpkgs.git HEAD` succeeded using only this private key, with `-F /dev/null`, `IdentityAgent=none`, `IdentitiesOnly=yes`, `BatchMode=yes`, and strict checking against existing GitHub host keys. Repository read access is verified independently of any SSH agent or other configured identities. Write permission is user-configured but has not been push-tested; no push was attempted. The login and dedicated-key fingerprints were rechecked and remain unchanged.
- Use the local shared GitHub private key at `~/.ssh/id_nixos_vm_github`, intended as an unencrypted Ed25519 key for unattended use in clones. Prefer a GitHub deploy key with write access scoped to this repository. The guest username is `dbalatero`. Keep private key material outside Git and all Nix build inputs.
- The recovery password is stored in 1Password item UUID `yklwrusohu3uus3bpnua7v27ky`. Integration verification succeeded using dummy item UUID `rzklmlol5hzb2qsyitgrca5q7a`; the real recovery item was subsequently read through the protected interface for image preparation and console testing, without printing its value. Do not print secret values or put them in command arguments, environment variables, logs, Git, or the Nix store.
- On 2026-09-26, enabled the NixOS 1Password CLI and GUI integration modules with `dbalatero` as the polkit policy owner, removed the duplicate home-manager GUI package, and successfully ran `./bin/switch` on `panther`. `op --version` reports `2.34.1` from `/run/wrappers/bin/op`. The initial dummy read returned "No accounts configured for use with 1Password CLI"; after the user approved the desktop prompt, subsequent reads succeeded and the dummy password matched the user-provided expected value in memory, with the value suppressed entirely. Desktop integration may require future app unlocks or authentication approvals, so this test does not guarantee permanently unattended access. If integration stops working, check Settings > Security > Unlock using system authentication and Settings > Developer > Integrate with 1Password CLI, and retry the dummy item before the real secret.
- Prefer Python scripts with `argparse`: expose flags for noninteractive iteration and use interactive TTY prompts for missing required inputs. Without a TTY, fail clearly on missing inputs. Password options accept a 1Password item reference or request an explicit hidden terminal prompt in the builder, never literal secret values. Password-file and password-FD input modes are not supported.
- Embed the local committed repository snapshot, including implementation commits that have not been pushed. Do not rely on a fresh remote clone to contain the new code. Preserve a real writable Git repository and configure its GitHub origin for later user-managed synchronization.
- Record local verification limits honestly. Diagnose QEMU/KVM availability, and distinguish software-emulated or unavailable tests from completed hardware-accelerated tests. Laptop login and Proxmox-specific behavior remain unverified until actually tested.

## Design decisions

- Use the NixOS `qcow` image variant for x86_64 Linux. Author, evaluate, build, and test on the current x86_64 Linux desktop.
- Embed the approved public keys from `hosts/proxmox-base/authorized_keys` for `dbalatero`. Disable SSH password login; allow passwordless `sudo`. After the Nix build succeeds, obtain the console recovery password from the verified 1Password integration or an explicitly requested hidden terminal prompt. Default both the builder and smoke helper to 1Password item `yklwrusohu3uus3bpnua7v27ky` when no source is supplied. `--password-op-item` selects an alternate item. The UUID is an item reference, not a credential; 1Password authentication remains required. Offer hidden confirmation prompts only with the builder's explicit `--password-prompt` flag and a TTY. The smoke helper tests console recovery by default; `--skip-console` explicitly omits that check and password read. Console recovery requires access to the VM console.
- Inject a salted password hash and a shared, write-capable GitHub SSH private key only after the Nix build. Neither secret enters Git, command arguments, logs, or the Nix store. Every clone intentionally shares them. A new template does not rotate existing clones; rotate each VM when needed.
- Use `~/code/proxmox-base` on the Linux desktop for user-managed artifacts. Nix keeps the secret-free build output in `/nix/store`; copy it into this workspace before adding secrets. The build script sets `umask 077`, creates or fixes the workspace to `0700`, and allows an explicit work-directory override. Directories and executable helpers are `0700`, finished images `0400`, and writable test copies or temporary files `0600`.
- Keep the prepared template image unbooted. Boot only disposable copies so cloned VMs generate their own machine identity and SSH host keys.
- Generated operator scripts may stage host files and print next commands, but do not commit or push automatically. The agent makes frequent small implementation commits during this task and never pushes.

## Disk sizing

- Give the template a modest minimum virtual disk size with enough free space for a NixOS rebuild; start with 20 GiB and adjust after the desktop smoke test. Every clone starts at least this large. A larger virtual disk does not immediately consume that much physical storage on thin-provisioned Proxmox storage, but actual usage must still be monitored.
- For a VM that needs more space, resize that clone's disk in Proxmox before its first boot. Keep the template size unchanged. Make sure the image enables root partition growth (`boot.growPartition`) and root filesystem growth (`fileSystems."/".autoResize`); verify both with `lsblk` and `df -h /` after boot.
- Growing a disk later follows the same pattern: enlarge it in Proxmox, reboot the guest if needed, and verify partition and filesystem sizes. Do not rely on shrinking a clone back below the template size. Consider a separately configured data disk for services whose data needs independent sizing.

## Implementation evidence (2026-09-26)

Host diagnosis outside the agent sandbox confirms `panther` has an Intel Core i9-9900K with VT-x, loaded `kvm_intel` and `kvm` modules, and an accessible `/dev/kvm` (mode `0666`, owner/group `root:kvm`). Its existing Nix configuration already declares `boot.kernelModules = ["kvm-intel"]` and advertises the `kvm` system feature. No KVM configuration change or reboot is needed. The earlier missing `/dev/kvm` observation came from sandbox isolation; run the image build and boot tests with host device access. The full local guest test subsequently passed using KVM, as recorded in Phase 2.

The image definition, preparation script, cloned-VM bootstrap, and local smoke-test helper are implemented. The `.#proxmox-base` package resolves to the qcow image variant, with UEFI/GPT, an EFI system partition, and ext4 root. Evaluate the image via `packages.x86_64-linux.proxmox-base` or `nixosConfigurations.proxmox-base.config.system.build.images.qcow`; evaluating the unextended base host's ordinary toplevel omits the image variant's disk/boot configuration.

All 27 unit tests pass (`python3 -B -m unittest discover -s tests -p 'test_*.py'`), including six bootstrap safety tests. They cover malformed input before mutation, dirty checkout and host collisions, preservation of unpushed commits and refusal of divergent history, ambiguous interface selection, Nix evaluation of generated static networking with escaped description text, and BIOS root-disk discovery. A generated static guest with the actual reusable system and home modules plus representative EFI hardware filesystems fully evaluates to a NixOS system derivation. The qcow image derivation also evaluates. These implementation checks complement the completed image build and full local guest test recorded in Phase 2.

`bin/build-proxmox-base-image --help`, `bin/test-proxmox-base-image --help`, and `bin/bootstrap-nixos-vm --help` document the implemented interfaces. The README records the actual flags and defaults. Image preparation and the full local KVM smoke test passed; the user-operated Proxmox trial remains pending. Phase 1 checkmarks below mean implementation/evaluation complete; Phase 2 records runtime verification separately.

## Full PDE update (verified)

The user explicitly requested the complete `home/modules/pde` in the image. `home/modules/proxmox-vm` now imports both `../core` and `../pde`, plus the NixVim and Stylix Home Manager modules. Shared `hosts/common/nixos-vm` wiring supplies Home Manager, the Claude/Codex/Neovim overlays, input arguments, zsh, and nix-ld to both the base image and generated VM hosts. Bootstrap-generated flake entries pass `inputs` to this shared wiring, so the first rebuild retains the full PDE. No GUI module was added.

The canonical source remains `/home/dbalatero/.config/nixpkgs`; PDE writable configuration symlinks point into that checkout. VM overrides keep the dedicated GitHub key with strict host checking and no SSH agent, use the installed zsh for tmux, and make the `switch` alias run the local `bin/switch` without an implicit `git pull origin main`. Home Manager now owns `~/.ssh/config`, so preparation no longer injects a competing file; the private key and verified `known_hosts` remain post-build inputs.

The PDE-enabled secret-free image successfully built at `/nix/store/7dn90aijywvyjlrqyjwlzwkyn1hq15bz-nixos-disk-image`. Image preparation and the complete local KVM smoke test passed. The report records `pde_before_bootstrap: true` and `pde_after_rebuild: true`, alongside successful console recovery, GitHub read access, bootstrap, a subsequent package rebuild, and clone identity/growth checks.

## Phase 1: Implement and evaluate on the Linux desktop

This phase produces reviewable code and validates it before the local image build and boot tests.

### 1. Define the base image

- [x] Add `nixosConfigurations.proxmox-base` to `flake.nix`, using `system = "x86_64-linux"` and a dedicated module under `hosts/proxmox-base/`.
- [x] Configure a headless guest with DHCP, SSH, QEMU guest agent, and `dbalatero` in `wheel`. First login must already provide Nix flakes, `nixos-rebuild`, `nixos-generate-config`, `sudo`, an editor, Git, and bootstrap dependencies.
- [x] Confirm the selected `qcow` image layout has a growable root partition and filesystem; set `boot.growPartition` and `fileSystems."/".autoResize` if the image module does not already provide them.
- [x] Remove or override `hosts/common/nixos/users.nix`'s `initialPassword = "changeme"` for this image and its generated VM hosts. Keep the user in `wheel` with passwordless `sudo`. Configure the user to load a root-only password hash file from the guest filesystem, outside the Nix store, so the console password survives rebuilds.
- [x] Read the user-created `hosts/proxmox-base/authorized_keys` for `dbalatero`; validate the public keys and fingerprints, and ensure no private key material is tracked. The `authorized_keys` filename is intentionally allowed for these committable public keys.
- [x] Add ignored paths for image-only private key material. Keep the actual GitHub private key outside the Nix expression and all Nix build inputs.
- [x] Update `lab/README.md` with the confirmed login prerequisites, template disk minimum, and console recovery method.

### 2. Write the image scripts

- [x] Add `bin/build-proxmox-base-image` as the sole user-facing entry point. Build `.#proxmox-base` as a `qcow` image, copy the secret-free result into the workspace, then obtain the recovery password using a configured protected source, defaulting to the configured 1Password item, with hidden confirmation prompts available through explicit `--password-prompt`. Produce a separate prepared qcow2 with a 20 GiB minimum virtual size and print only its path as the import artifact. Never report a partial image as ready.
- [x] In the build script or an internal preparation helper, hash the supplied password and inject its hash into a root-only guest file. Inject the local `~/.ssh/id_nixos_vm_github`, a verified GitHub `known_hosts` entry, and a real writable copy of the local committed repository snapshot at `/home/dbalatero/.config/nixpkgs`. Preserve `.git` and the unpushed implementation commits, set correct ownership and permissions, configure `origin` as `git@github.com:dbalatero/nixpkgs.git` and an appropriate upstream branch, and explicitly select the injected key for GitHub SSH. Ensure Git name/email and SSH identity work on first login. Exclude unrelated uncommitted changes and host-local Git metadata that should not enter the image.
- [x] Validate input images, private key, workspace ownership, and required Linux image tools before making a final image. Pass secrets between subprocesses through protected pipes, never arguments or environment variables; these internal pipes are not user-facing password input modes. Keep any required temporary files `0600` inside the workspace and remove them on success or failure; finish images as `0400`. Keep boot-test copies `0600`, avoid overwriting an existing prepared image, and do not modify the import artifact.
- [x] Update the README with the build command, flags, protected secret sources, explicit TTY password prompts, and final artifact location once the script interface is fixed.

### 3. Write the cloned VM bootstrap script

- [x] Add `bin/bootstrap-nixos-vm <hostname>` using Python `argparse` with flags for description, static IP, gateway, DNS, and profile, and TTY prompts for missing required inputs. Document the expected values and defaults; support fully noninteractive use when inputs are supplied.
- [x] Have it generate hardware configuration on the cloned VM, create `hosts/<hostname>` and `home/hosts/<hostname>`, add `nixosConfigurations.<hostname>` to `flake.nix`, and stage the new files.
- [x] Validate arguments and existing-host collisions before changing files. Print the changes and the manual commit commands, then run `sudo nixos-rebuild switch --flake .#<hostname>`.
- [x] Before editing, fetch the latest repo state with a fast-forward-only update when the checkout is clean. Preserve local unpushed commits embedded in the image; do not reset to the remote branch. Provide an explicit way to skip network synchronization for local tests. Explain how to recover if the VM was cloned from an older template, histories diverged, or the working tree has changes; never discard local work or push automatically.
- [x] Generate VM networking and bootloader settings for the actual Proxmox hardware. Do not copy the current template's hardcoded `eth0` or `/dev/sda` assumptions. Keep DHCP as the safe default; validate optional static IP, gateway, and DNS settings before switching.
- [x] Preserve the working Git checkout and SSH key across the first rebuild. Verify that the new host module includes the needed user, SSH, Git, editor, sudo, and home-manager setup.
- [x] Update the README with the bootstrap command's actual flags and defaults, the edit/rebuild path, and the manual commit/push step.

### 4. Validate implementation before building

- [x] Stage newly created Nix files with `git add` so flake evaluation includes them; make small implementation commits after relevant checks pass. Never push.
- [x] Parse changed Nix files with `nix-instantiate --parse <file> >/dev/null`, compile-check Python scripts, and check any shell wrappers with `bash -n` and `shellcheck` if available.
- [x] Evaluate the image derivation without building it, for example `nix eval --raw .#nixosConfigurations.proxmox-base.config.system.build.images.qcow.drvPath`. Fix option errors revealed by evaluation.
- [x] Confirm the password hash file is read from the guest filesystem during activation, not during the Nix build; validate that the chosen user-management mode accepts it.
- [x] Exercise script help, argument validation, and safe failure paths with disposable inputs. Do not put the real GitHub private key into a test fixture.
- [x] Keep untested steps in the README marked as planned. Record detailed Linux test and Proxmox import commands here until they have been run.
- [x] Review and commit task changes in small pieces. Verify the repository snapshot selected for image preparation includes these local commits without requiring a push. Never include private key material.

**Build complete:** the PDE-enabled prepared artifact embeds committed snapshot `35a6d3e` and passed the full local runtime test. Later smoke-test and documentation commits do not change that embedded snapshot.

## Phase 2: Linux desktop

The PDE-enabled image’s full local KVM smoke test passed on 2026-09-26, including PDE availability before bootstrap and after rebuilding. The writable repository at `/home/dbalatero/.config/nixpkgs` is the canonical VM configuration source: bootstrap creates its host/home modules and flake entry there, and both verified rebuilds used that checkout's flake.

- Prepared, never-booted artifact: `/home/dbalatero/code/proxmox-base/proxmox-base-prepared-35a6d3e.qcow2`; embedded commit `35a6d3e`.
- Secret-free build output: `/nix/store/7dn90aijywvyjlrqyjwlzwkyn1hq15bz-nixos-disk-image/nixos-proxmox-base.qcow2`.
- Complete report: `/home/dbalatero/code/proxmox-base/smoke-5pe5xgri/report.json`, with `passed: true`, `acceleration: kvm`, and bootstrap/rebuild, GitHub read, and console recovery checks enabled.
- Original artifact SHA-256 before and after tests: `95ae58b2d8d790528d2c94ba43aac4faa8d3194d30db743f2c963623335a0596` (unchanged).
- The 20 GiB clone's root filesystem grew to 20,691,124,224 bytes; the 28 GiB clone's root grew to 29,147,344,896 bytes. The clones had distinct machine IDs and SSH host-key fingerprints. The 20 GiB clone had 12,042,465,280 bytes (11.22 GiB) free before the tests and 11,646,259,200 bytes (10.85 GiB) free afterward; the prepared image occupies about 7.3 GiB on the desktop.
- The live-hostname issue was fixed declaratively: the shared module activates `networking.hostName` after `/etc` activation. The complete rerun verified the new live hostname without a reboot, the first bootstrap rebuild, and another rebuild adding `hello`.

- [x] Verify `op` against the dummy item, then prepare the image using the local committed snapshot, dedicated GitHub key, and protected recovery-password source. Preserve the secret-free build output for repeatable preparation.
- [x] Audit workspace permissions and remove disposable test disks. All workspace directories are `0700`; all 45 regular files are `0400` or `0600`. No `.prepare-` temporary directories or disposable test disks remain. The current tested PDE artifact and reports remain; the earlier minimal `51cb791` image is retained as a previous version. The successful smoke helper removed its disposable disks automatically.
- [x] Check tracked Git blobs for private-key headers and literal crypt password hashes: zero matches. Review preparation paths to confirm private inputs and the password hash are injected after the Nix build, outside the Nix store. These targeted checks and path review are not a forensic scan of all historical host data.
- [x] Boot private disposable copies under QEMU/KVM with SSH forwarding. Verify DHCP, guest-agent operation before and after rebuilds, desktop-key login, rejected SSH password login, passwordless sudo, and actual serial-console recovery login before and after rebuilds.
- [x] Confirm the laptop public key is embedded.
- [ ] Test login from the laptop using its private key when a guest is reachable; public-key presence alone does not prove that login path.
- [x] Verify root growth to the 20 GiB minimum and an enlarged 28 GiB clone, with enough space for both tested NixOS rebuilds.
- [x] Verify the writable checkout, GitHub SSH origin, Git author settings, editor and bootstrap tools, flake evaluation, and local `nixos-rebuild`. Verify GitHub repository read access from the guest using the dedicated key. No pushes were performed; write access remains untested.
- [x] Document the actual build/test commands and artifact location in the README.
- [x] Exercise bootstrap, live hostname activation, a subsequent package edit/rebuild, complete PDE availability before and after rebuilds, preservation of SSH and console recovery, distinct machine identities/host keys, and root growth on disposable local VMs.
- [x] Record the prepared artifact, documented import guidance, local test evidence, and remaining laptop/Proxmox checks for the user. No Proxmox changes or GitHub pushes were performed.

The DHCP path was exercised in the full local test. Static-network arguments and generated Nix configuration passed automated checks, but a live static-network trial remains untested. Actual Proxmox import, networking, disk bus, and clone behavior still require Phase 3.

## Interactive local testing (2026-09-28)

Use `bin/boot-proxmox-base-image ~/code/proxmox-base/proxmox-base-prepared-bbe6355.qcow2 --vm-dir ~/code/proxmox-base/manual-test` for manual console and SSH checks. The newer artifact's recorded `smoke-iq9zz8cm/report.json` reports a full KVM pass. On 2026-09-28, its SHA-256 was recomputed and matched the report: `6aa3bf4d1e460461fc833026dc572d79109d33d9231038a5094b3138c7d52852`. The earlier runtime evidence above remains unchanged.

Without `--vm-dir`, the helper creates a new private `manual-*` directory under `~/code/proxmox-base`. Defaults are 4 CPUs, 4096 MiB RAM, localhost SSH port 22222, and KVM when available (software emulation otherwise). The helper boots a private persistent overlay, copies the firmware into the VM directory, leaves the prepared source untouched, and prints SSH and relaunch commands. Keep the original image available at the same path and reuse the same source and `--vm-dir` to retain guest changes. Console login uses `dbalatero` and the recovery password from 1Password; the helper does not retrieve that password. Use `sudo poweroff` in the guest for a clean shutdown. Networking is local NAT with localhost SSH forwarding, not Proxmox/LAN bridging.

Interactive launcher verification on 2026-09-30: the guest reached its console login prompt, SSH login as `dbalatero` succeeded, the canonical repository was present, a persistence marker was created, and `sudo poweroff` shut down the guest with launcher exit status 0. Relaunching with the same `--vm-dir` reached the console prompt again, retained the marker, accepted SSH with strict host-key checking using the same host key, and shut down cleanly again with exit status 0. The launcher verified the source image hash was unchanged on resume. These launcher checks did not retrieve or enter the console recovery password.

## Networking context for the next phase

Confirmed by the user: a UniFi Dream Machine provides DHCP on `192.168.1.2`–`192.168.1.200`; addresses `.201`–`.254` are set aside for static assignments. The gateway is `192.168.1.1`, and the existing Raspberry Pi Pi-hole at `192.168.1.169` supplies LAN DNS. Existing static assignments are TrueNAS at `192.168.1.201`, the iMessage Mac Mini server at `192.168.1.209`, and the Proxmox host at `192.168.1.250`. The user chose per-machine static Nix configuration for VMs, with a repository inventory to record assignments, reject known duplicates, and suggest available addresses. Keep the template on DHCP so new clones do not start with the same static address.

The user owns `netcat.cloud`, but service names are not configured; the registrar and DNS hosting provider are not yet known. The user prefers private remote access through a VPN. Exposing Plex to friends later is a possibility, not a decided requirement.

Proposals still to confirm: attach VMs to the Proxmox LAN bridge and use a separate Caddy VM for HTTPS service routing. Machine DNS names would resolve directly to their VM addresses, while HTTPS service names would resolve to the proxy. Keep the existing Pi-hole during initial VM/proxy testing; a later Pi-hole migration or redundant DNS setup remains to be planned. No live network, DNS, VPN, or reverse-proxy configuration has been applied as part of this discussion.

### Address inventory and bootstrap workflow

`lab/network.json` is the tracked inventory. It defines `subnet`, `dhcp_range`, `static_range`, `gateway`, `dns`, and a `machines` array with `ip`, `hostname`, and `comment` fields per entry. The user chose JSON with explicit comments as data so the script can use Python's standard library without a YAML dependency. Writes use human-readable two-space indentation and a trailing newline. The initial entries cover the gateway, Pi-hole, TrueNAS, iMessage Mac Mini, and Proxmox host. Labels for these existing devices are descriptive, not verified DNS names.

`bin/bootstrap-nixos-vm --suggest-ip` reads the current local inventory and prints a suggested CIDR without fetching, allocating, or requiring a prepared guest. Initially the suggestion is `192.168.1.202/24`, meaning unallocated in the repository, not confirmed unused on the LAN. `--static-ip auto` selects an available static address during bootstrap; explicit `--static-ip ADDRESS/PREFIX` remains supported. The homelab static range excludes the DHCP pool. The inventory provides the default gateway `192.168.1.1` and DNS `192.168.1.169` for this subnet, with CLI overrides available. Other subnets require explicit gateway and DNS settings.

Without arguments at a TTY, bootstrap prompts for hostname and IP, offering `auto` or `dhcp`. Hostname-only invocations retain DHCP, preserving the existing local NAT test workflow and the DHCP base image. Bootstrap normally updates the clean repository before selecting or checking addresses. A successful static selection is recorded and staged with the generated host configuration, including with `--no-switch`; known duplicate allocations are rejected before host generation. Scripts never commit or push.

The inventory is not a global allocator and does not discover UniFi or manually configured devices. Keep external-device entries current and provision sequentially: review, commit, and manually push each new allocation before another checkout provisions a VM. Concurrent or stale checkouts can otherwise choose the same address; `--skip-update` is intended for local/offline tests and can miss new assignments. Maintain the inventory alongside later address changes or host retirement. Pi-hole DNS records remain separately managed.

An older prepared image can use these script changes without rebuilding the image: after the implementation is published manually, run `git pull --ff-only` in its clean canonical checkout before invoking bootstrap. The script's own update cannot reload Python code already running from an older snapshot. Reconcile any divergent Git history without resetting guest work. Run static bootstrap through the Proxmox console because its rebuild can interrupt SSH. Runtime verification remains limited to the previously tested DHCP path until the user performs a live static Proxmox trial.

Verification on 2026-09-30: all 41 tests passed without skips, including 20 bootstrap tests covering the JSON inventory behavior and Nix evaluation of generated networking. A live Proxmox static-network trial remains untested.

## Phase 3: Proxmox template and first clone (user-operated later)

These steps are outside the current unattended run. The user will perform the actual Proxmox trial; keep them marked untested until that trial supplies evidence.

- [ ] Import the prepared, never-booted qcow2 into Proxmox. Set a compatible firmware mode and disk bus, enable the guest agent, and convert it directly to a template. Boot a clone for testing, never the template source disk.
- [ ] Clone the template. Resize this first clone's disk in Proxmox before booting it, choosing a size larger than the template; keep smaller service VMs at the template size.
- [ ] Boot the clone, verify the larger root partition and filesystem with `lsblk` and `df -h /`, then run `bin/bootstrap-nixos-vm <hostname> ...` with that VM's description, networking, and profile values.
- [ ] Confirm the clone has its own machine ID and SSH host keys. Confirm generated hardware configuration, host and home modules, flake entry, staged files, networking, and `nixos-rebuild switch` all succeed.
- [ ] Confirm key-only SSH login, passwordless `sudo`, and console password login still work after the clone's first `nixos-rebuild switch`. Test console login without relying on SSH so it is a real recovery path.
- [ ] Add a small package or service to the new host configuration, rebuild again, and verify it works. This proves the normal edit-and-rebuild loop beyond the bootstrap itself.
- [ ] Review, commit, and push from the VM manually to confirm GitHub write access.
- [ ] Replace the README's planned Proxmox and bootstrap steps with the verified clone, disk resize, login, bootstrap, rebuild, and recovery steps; remove its work-in-progress notice only after following it end to end.
- [ ] Record any desktop or Proxmox fixes in this plan and the scripts so the next clone follows the same procedure.
