# Proxmox NixOS Base Image Plan

## Goal

Create an x86_64 Linux `qcow2` base image for Proxmox. It boots headless NixOS, has this repo cloned at `/home/dbalatero/.config/nixpkgs`, accepts the laptop and desktop SSH public keys for login, has a shared console recovery password chosen during image preparation, and contains a shared GitHub SSH write key for repo push/pull.

Develop and evaluate the configuration on the macOS M1 Air. Build and boot the image on the AMD NixOS desktop, then import it into Proxmox and convert it to a VM template.

**First-login success:** after cloning the template, SSH in as `dbalatero`, open the existing writable repo, run one bootstrap command to name and configure that VM, edit its NixOS configuration, rebuild locally, then commit and push to GitHub. No separate installation, manual repo clone, or hand-edited system file should be needed.

## Key Decisions

- Use the NixOS `qcow` image variant for the primary image.
- Build the x86_64 Linux image on the AMD NixOS desktop. The Mac is for authoring, parsing, evaluation, and script checks.
- Use `~/code/proxmox-base` on the AMD desktop as the default workspace for all user-managed image artifacts, preparation, and local smoke-test copies. It is outside the Git repository. Nix still keeps the secret-free build output in `/nix/store`; copy the image into the workspace before adding secrets. The build script creates it with mode `0700` or fixes its mode to `0700`, sets `umask 077`, and allows an explicit work-directory override.
- Keep files in that workspace owner-only: completed raw and prepared images `0400`, writable image copies and temporary files `0600`, and subdirectories or executable helpers `0700`. Never put secret-bearing output under a world-readable path or a Nix build output.
- Embed the laptop and desktop SSH public keys in the declared `dbalatero` user; public keys may be committed.
- Make `bin/build-proxmox-base-image` the single user-facing command. Each time it creates a prepared qcow2 image, it prompts for the `dbalatero` recovery password after the Nix build succeeds. On the first run, create a long, unique password in 1Password and paste it; on later runs, retrieve and paste that same password. The script does not save a copy outside the image. Inject only a protected password hash into the guest image; never put the password or hash in Git, command arguments, logs, or the Nix store.
- Disable SSH password authentication and allow passwordless `sudo` after public-key login. The password is for local Proxmox console recovery if SSH keys are lost or SSH is unavailable; recovery still requires access to the VM console.
- All clones intentionally share this recovery password. Changing the template later does not rotate existing clones; update each clone if rotation is needed.
- The shared GitHub SSH private key must never enter Git or the Nix store. The preparation script reads it from an ignored local path and injects it only after the image build.
- The shared GitHub SSH key is intentionally write-capable and duplicated into every VM cloned from the template.
- Rotate the shared GitHub key if a clone is compromised or decommissioned.
- Use the prepared but never-booted image as the template source. Boot only disposable copies so each clone generates its own machine identity and SSH host keys.
- New host commits remain manual; scripts may stage files and print next commands, but must not commit automatically.

## Phase 1: Work on the macOS M1 Air

This phase produces reviewable code and checks it without building or booting a Linux image.

### 1. Define the base image

- [~] Add `nixosConfigurations.proxmox-base` to `flake.nix`, using `system = "x86_64-linux"` and a dedicated module under `hosts/proxmox-base/`.
- [ ] Configure a headless NixOS guest with SSH, the `dbalatero` user, QEMU guest agent, Git, bootstrap dependencies, and DHCP-friendly networking.
- [ ] Ensure a first SSH login already has `nix`, `nixos-rebuild`, `nixos-generate-config`, `sudo`, an editor, Git, and flake support. Give `dbalatero` a documented sudo path for local rebuilds.
- [ ] Remove or override `hosts/common/nixos/users.nix`'s `initialPassword = "changeme"` for this image and its generated VM hosts. Keep the user in `wheel` with passwordless `sudo`. Configure the user to load a root-only password hash file from the guest filesystem, outside the Nix store, so the console password survives rebuilds.
- [~] Add the laptop and desktop SSH login public keys for `dbalatero`; verify both fingerprints and that only `.pub` files are tracked.
- [~] Add ignored paths for image-only private key material. Keep the actual GitHub private key outside the Nix expression and all Nix build inputs.

### 2. Write the image scripts

- [ ] Add `bin/build-proxmox-base-image` as the single entry point: create or validate the `~/code/proxmox-base` workspace, build the `qcow` image from `.#proxmox-base`, copy the secret-free raw image there, prompt for and confirm the recovery password with hidden input after the build succeeds, prepare a separate copy, and print the final qcow2 path for Proxmox import. Never treat the raw Nix build output as the ready-to-import template.
- [ ] Have the build script call a preparation helper (which may be `bin/prepare-proxmox-base-image`) to generate a salted password hash from the entered password, inject the hash into a root-only guest file, inject `~/.ssh/id_github` with restrictive permissions, install a verified GitHub `known_hosts` entry, and place a real clone of `git@github.com:dbalatero/nixpkgs.git` at `/home/dbalatero/.config/nixpkgs` with the correct ownership and `origin`. Pass the password to the helper only through a protected pipe or file descriptor, never as a command argument or environment variable.
- [ ] Make the image's checkout a normal writable Git clone with an upstream branch. Ensure Git name/email and SSH identity are usable at first login, whether supplied by the base image or activated home-manager configuration.
- [ ] Make the build and preparation steps fail clearly when the image, private key, or required Linux image tools are missing. They must not print or copy the private key, password, or password hash into logs, Git, or the Nix store; use protected temporary files only if the image tools require them. If preparation fails, do not report an incomplete image as ready.
- [ ] Create temporary files only inside the workspace with mode `0600`, remove them on success or failure, and verify the final image is `0400` after preparation. Make a separate `0600` copy for any boot test so the import artifact remains unmodified.

### 3. Write the cloned VM bootstrap script

- [ ] Add `bin/bootstrap-nixos-vm <hostname>` with flags for description, static IP, gateway, DNS, and profile. Document the expected values and defaults.
- [ ] Have it generate hardware configuration on the cloned VM, create `hosts/<hostname>` and `home/hosts/<hostname>`, add `nixosConfigurations.<hostname>` to `flake.nix`, and stage the new files.
- [ ] Validate arguments and existing-host collisions before changing files. Print the changes and the manual commit commands, then run `sudo nixos-rebuild switch --flake .#<hostname>`.
- [ ] Before editing, fetch the latest repo state with a fast-forward-only update when the checkout is clean. Explain how to recover if the VM was cloned from an older template or the working tree has changes; never discard local work.
- [ ] Generate VM networking without assuming the interface is named `eth0` (the current `hosts/template/configuration.nix` does). Keep DHCP working until the host-specific network configuration succeeds, and make static IP configuration optional or safely validated.
- [ ] Preserve the working Git checkout and SSH key across the first rebuild. Verify that the new host module includes the needed user, SSH, Git, editor, sudo, and home-manager setup.

### 4. Check what can be checked on the Mac

- [ ] Stage newly created Nix files with `git add` so flake evaluation includes them; do not commit automatically.
- [ ] Parse changed Nix files with `nix-instantiate --parse <file> >/dev/null` and shell scripts with `bash -n <script>`; run `shellcheck` if available.
- [ ] Evaluate the image derivation without building it, for example `nix eval --raw .#nixosConfigurations.proxmox-base.config.system.build.images.qcow.drvPath`. Fix option errors revealed by evaluation.
- [ ] Exercise script help, argument validation, and safe failure paths with disposable inputs. Do not put the real GitHub private key into a test fixture.
- [ ] Document the exact Linux build, QEMU smoke test, Proxmox import, and clone bootstrap commands before leaving this phase.
- [ ] Review the staged changes, then commit and push them manually so the AMD desktop can pull the same revision. Never include the private key in this transfer.

**Mac handoff:** tracked configuration and scripts have passed parsing, evaluation, and script checks; the reviewed commit is available to the AMD desktop; the real private key remains outside Git and the Nix store. Any Linux-only checks are listed for Phase 2.

## Phase 2: AMD NixOS desktop

- [ ] Pull the reviewed commit from the Mac and confirm the working tree contains the expected image configuration and scripts.
- [ ] Run `nixos-rebuild build-vm --flake .#proxmox-base` with its output link placed inside `~/code/proxmox-base`, then boot the VM for a basic configuration check. Nix store paths and symlink modes are managed by Nix; do not create a default `result` link in the Git repository.
- [ ] Run `bin/build-proxmox-base-image` using the local ignored GitHub key. When prompted, create the recovery password in 1Password or paste the existing one. The script produces the prepared qcow2; keep the unprepared Nix image available for repeatable builds.
- [ ] Confirm `~/code/proxmox-base` and any subdirectories are `0700`, finished images are `0400`, and any writable test copies are `0600`. Confirm no secret-bearing artifacts or temporary files are left outside that workspace.
- [ ] Boot the prepared qcow image under QEMU with SSH port forwarding.
- [ ] Verify SSH login with the authorized public keys, guest agent availability, DHCP networking, and the repo at `/home/dbalatero/.config/nixpkgs`.
- [ ] Verify both the laptop and desktop public keys can log in, SSH password login is rejected, `sudo` works without a password after login, and the recovery password works at the VM console.
- [ ] Verify the repo `origin` is `git@github.com:dbalatero/nixpkgs.git` and `ssh -T git@github.com` uses `~/.ssh/id_github`.
- [ ] From the first SSH login on a disposable image copy, verify the repo is writable and Git author settings, editor, flake evaluation, and `sudo nixos-rebuild` are available without installing anything.
- [ ] Confirm the private key is absent from Git and the Nix store before importing the prepared image.

## Phase 3: Proxmox template and first clone

- [ ] Import the prepared, never-booted qcow image into Proxmox, set the intended VM hardware and guest agent options, and convert it directly to a template. Boot a clone for testing, never the template source disk.
- [ ] Clone the template and run `bin/bootstrap-nixos-vm <hostname> ...` with that VM's description, networking, and profile values.
- [ ] Confirm the clone has its own machine ID and SSH host keys. Confirm generated hardware configuration, host and home modules, flake entry, staged files, networking, and `nixos-rebuild switch` all succeed.
- [ ] Confirm key-only SSH login, passwordless `sudo`, and console password login still work after the clone's first `nixos-rebuild switch`. Test console login without relying on SSH so it is a real recovery path.
- [ ] Add a small package or service to the new host configuration, rebuild again, and verify it works. This proves the normal edit-and-rebuild loop beyond the bootstrap itself.
- [ ] Review, commit, and push from the VM manually to confirm GitHub write access.
- [ ] Record any desktop or Proxmox fixes in this plan and the scripts so the next clone follows the same procedure.
