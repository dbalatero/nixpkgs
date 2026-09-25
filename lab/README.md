# Add a NixOS VM to the homelab

> Work in progress. The image and bootstrap scripts below are planned; verify this guide during the first Proxmox clone.

## Create the template (once, on the AMD desktop)

1. Pull the reviewed configuration, then run `bin/build-proxmox-base-image` from the repo. When prompted, create the console recovery password in 1Password or paste the existing one.
2. The prepared qcow2 is saved under `~/code/proxmox-base`. Test a copy, import the untouched image into Proxmox, and convert it to a template. Do not boot the template disk itself.

## Create a VM

1. Clone the NixOS template in Proxmox. If this service needs more than the template's 20 GiB disk, resize the clone before its first boot.
2. Boot the clone and find its DHCP address in Proxmox or your network's DHCP leases.
3. SSH in as `dbalatero` from the laptop or desktop using its SSH key.
4. In `/home/dbalatero/.config/nixpkgs`, run `bin/bootstrap-nixos-vm <hostname>` with the needed network and profile flags. The script creates the host configuration and runs the first rebuild.
5. Edit `hosts/<hostname>/configuration.nix` for the service, then run `sudo nixos-rebuild switch --flake .#<hostname>` from the repo.
6. Check the service, review the staged changes, then commit and push them to GitHub manually.

SSH password login is disabled. If both SSH keys are unavailable, use the Proxmox console and the recovery password from 1Password. The password and GitHub write key are shared by clones of this template.
