# Proxmox NixOS Base Image Plan

## TODO
- [x] Create this tracked plan file and keep it updated as implementation progresses.
- [~] Add a `proxmox-base` NixOS configuration for image builds.
- [~] Add tracked SSH login public keys for the `dbalatero` NixOS user.
- [~] Add ignored local secret paths for image-only private key material.
- [ ] Add scripts to build and prepare the qcow image.
- [ ] Add a per-VM bootstrap script.
- [ ] Document local Linux testing and Proxmox import workflow.
- [ ] Run syntax and feasibility checks.

## Summary
Create a Linux-built `qcow2` base image for Proxmox. The image boots NixOS, has this repo cloned at `/home/dbalatero/.config/nixpkgs`, includes SSH public keys for login, and contains a shared GitHub SSH write key for repo push/pull.

Build happens on the Linux desktop, the image is smoke-tested locally with QEMU, then imported into Proxmox and converted into a VM template.

## Key Decisions
- Primary image format is `qcow2` via the NixOS `qcow` image variant.
- Image builds happen on the Linux desktop, not macOS.
- Login SSH public keys may be committed as public key material.
- The shared GitHub SSH private key must never enter Git or the Nix store.
- The shared GitHub SSH key is intentionally write-capable and duplicated into every VM cloned from the template.
- New host commits remain manual; scripts may stage files and print next commands, but must not commit automatically.

## Implementation Shape
- Add `nixosConfigurations.proxmox-base` for a minimal VM image:
  - Headless NixOS.
  - SSH enabled.
  - `dbalatero` user.
  - QEMU guest agent.
  - Git and bootstrap dependencies.
  - DHCP-friendly networking so cloned VMs boot before host-specific static config exists.
- Add image scripts:
  - `bin/build-proxmox-base-image` builds `qcow` from `.#proxmox-base`.
  - `bin/prepare-proxmox-base-image` injects the shared GitHub key, `known_hosts`, and a real Git clone of this repo into a qcow image.
- Add `bin/bootstrap-nixos-vm <hostname>`:
  - Accepts flags for description, static IP, gateway, DNS, and profile.
  - Generates hardware config on the cloned VM.
  - Creates `hosts/<hostname>` and `home/hosts/<hostname>`.
  - Inserts the `nixosConfigurations.<hostname>` entry.
  - Stages files with Git.
  - Runs `sudo nixos-rebuild switch --flake .#<hostname>`.

## Test Plan
- On the Linux desktop:
  - Run `nixos-rebuild build-vm --flake .#proxmox-base` and boot it.
  - Build and boot the prepared qcow under QEMU with SSH port forwarding.
  - Verify SSH login works with authorized keys.
  - Verify the repo clone exists and `origin` is `git@github.com:dbalatero/nixpkgs.git`.
  - Verify `ssh -T git@github.com` uses `~/.ssh/id_github`.
- On a cloned Proxmox VM:
  - Run `bin/bootstrap-nixos-vm <hostname> ...`.
  - Confirm hardware config, flake entry, staged files, and `nixos-rebuild switch` all succeed.
  - Commit and push manually from the VM to confirm GitHub write access.
