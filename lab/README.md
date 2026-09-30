# Add a NixOS VM to the homelab

> The image includes the full terminal PDE and passed the full local KVM smoke test. The Proxmox import and clone trial remains work in progress for the user.

The tested, never-booted import artifact is `/home/dbalatero/code/proxmox-base/proxmox-base-prepared-35a6d3e.qcow2`, containing repository commit `35a6d3e`. The complete local report is `/home/dbalatero/code/proxmox-base/smoke-5pe5xgri/report.json`. Desktop SSH login, rejected password SSH, sudo, console recovery before and after rebuilds, the guest agent, GitHub read access, bootstrap with live hostname change, and another rebuild adding `hello` passed. Separate 20 GiB and 28 GiB clones grew their root filesystems and generated distinct machine IDs and SSH host keys. The original image's SHA-256 remained unchanged. The complete PDE was checked before bootstrap and after rebuilding. The image occupies about 7.3 GiB on the desktop; its 20 GiB virtual disk had 11.22 GiB free before the rebuild tests and 10.85 GiB afterward. Disposable test disks were removed; the tested PDE image, the previous minimal image, and reports remain in the private workspace.

The writable checkout at `/home/dbalatero/.config/nixpkgs` is the VM's canonical configuration source. Bootstrap writes the VM's host/home modules and flake entry there; all subsequent edits and rebuilds use that checkout's flake.

The base image and bootstrapped VMs now import `home/modules/core` and the complete `home/modules/pde` through the shared VM home module. This includes Neovim/NixVim, zsh, tmux, Git tools, mise, terminal theming, Claude Code, and Codex without importing the GUI configuration. The shared system module supplies the same overlays and Home Manager inputs to both the base image and generated hosts, enables zsh and nix-ld, and preserves the PDE after the first rebuild.

VM-specific settings select the injected GitHub deploy key, let Home Manager own SSH configuration, point tmux at the installed zsh, and make the `switch` alias rebuild the canonical local checkout without pulling another branch. Image preparation injects the key and `known_hosts`; it does not overwrite Home Manager's SSH configuration.

## Build and test on the Linux desktop

`panther` has an Intel i9-9900K, and KVM is already enabled by its existing Nix configuration. Host checks confirmed loaded KVM modules and an accessible `/dev/kvm`; no reboot or configuration change is needed. Run these commands with access to host devices: the agent sandbox hides `/dev/kvm`.

Login public keys live in `hosts/proxmox-base/authorized_keys`. The image uses account `dbalatero`, SSH key login, and passwordless sudo. Keep the shared GitHub deploy key at `~/.ssh/id_nixos_vm_github` with mode `0600`; it must have access to `dbalatero/nixpkgs`. Its public key is registered on that repository. GitHub read access has been verified; write access has not been push-tested.

Commit the changes you want inside the image. The builder embeds the current local committed snapshot, including unpushed commits, as a writable checkout at `/home/dbalatero/.config/nixpkgs`. It does not push or include unrelated uncommitted changes.

```bash
bin/build-proxmox-base-image
```

Both build and smoke-test commands default to 1Password item `yklwrusohu3uus3bpnua7v27ky`. This UUID identifies the item; it is not the credential and does not bypass 1Password authentication. The integration has passed a dummy-item check. The builder reads the item's `password` field after the secret-free build succeeds; 1Password may still request an unlock or desktop approval. Select another item with `--password-op-item OTHER_UUID`. Use the builder's explicit `--password-prompt` flag to enter and confirm the password with hidden input at a terminal. Never supply a literal password as a command argument.

The default final artifact is `~/code/proxmox-base/proxmox-base-prepared.qcow2`, a standalone image with a minimum 20 GiB virtual disk. Its mode is `0400`; the workspace is `0700`. `--work-dir` selects another private workspace, `--output` selects a new filename, and `--base-image` reuses a trusted secret-free qcow2 output. Existing prepared images are not overwritten. Required image tools are supplied from the pinned Nix packages.

Run the local smoke test on disposable copies:

```bash
bin/test-proxmox-base-image \
  ~/code/proxmox-base/proxmox-base-prepared.qcow2
```

The default desktop login key is `~/.ssh/id_rsa`; override it with `--ssh-key`. The helper uses KVM when available or software emulation otherwise (`--accel kvm|tcg` can require one), and tests a second clone enlarged to 28 GiB. The full run verified SSH, console recovery, separate machine identities, root growth, GitHub read access, bootstrap, and another rebuild. It prints the report path on success. Console recovery is tested by default using the configured 1Password item. Use `--skip-console` to explicitly omit it without reading a recovery password. Skipping rebuild, GitHub, or console checks limits what the run verifies. The prepared original is never booted. Laptop-key login still needs a test from the laptop.

## Boot interactively for manual testing

A newer prepared image is available at `~/code/proxmox-base/proxmox-base-prepared-bbe6355.qcow2`. Its recorded report, `~/code/proxmox-base/smoke-iq9zz8cm/report.json`, says the full KVM smoke test passed. The earlier artifact evidence above remains unchanged.

```bash
bin/boot-proxmox-base-image \
  ~/code/proxmox-base/proxmox-base-prepared-bbe6355.qcow2 \
  --vm-dir ~/code/proxmox-base/manual-test
```

Without `--vm-dir`, each launch creates a new private `manual-*` directory under `~/code/proxmox-base`. Defaults are 4 CPUs, 4096 MiB RAM, and localhost SSH port 22222; use `--cpus`, `--memory-mib`, or `--ssh-port` to change them.

Log in at the terminal console as `dbalatero` using the recovery password from 1Password. This helper does not read 1Password or type a password for you. To test key login separately, open another terminal and use the SSH command printed by the helper.

The guest runs from a private writable overlay and copied firmware files in `--vm-dir`; the prepared source remains untouched. Keep that source image at the same path. Guest changes persist when you rerun the printed launch command with the same source image and `--vm-dir`. Shut down cleanly with `sudo poweroff` inside the guest. QEMU's `Ctrl-a`, then `x` shortcut is an emergency exit, equivalent to cutting power. This is a local NAT test with SSH forwarded through localhost, not a guest attached to your LAN bridge.

The launcher was verified on 2026-09-30: console prompt, SSH login, writable canonical repository, clean shutdown, and relaunch with saved guest changes and the same SSH host key all passed. The source image hash remained unchanged. This launcher check did not retrieve or test the console password; enter it yourself to test that path.

## Import into Proxmox (user trial pending)

Import the untouched prepared qcow2 into a new VM with compatible UEFI firmware and a VirtIO disk controller, enable the QEMU guest agent, and attach the intended network bridge. Convert it directly to a template without booting it. The image has a GPT disk, EFI system partition, and ext4 root; use firmware settings compatible with that layout. Confirm the precise import settings during the first Proxmox trial.

## Create a VM

1. Clone the template. For a VM needing more than 20 GiB, enlarge its disk before first boot. Leave the template disk unchanged.
2. Boot the clone and find its DHCP address in Proxmox or your DHCP leases. SSH in as `dbalatero` using an authorized key.
3. In `/home/dbalatero/.config/nixpkgs`, update the clean checkout before invoking bootstrap so an older image uses the latest script and address inventory:

   ```bash
   git pull --ff-only
   ```

   The bootstrap updates the checkout again by default, but an already-running Python process does not reload its script after a pull. Updating first makes the new options available without rebuilding the base image. Publish the implementation from the desktop manually before pulling it into a VM. If Git reports divergence or local changes, resolve them without discarding guest work.
4. For a static address, use the Proxmox console for bootstrap: changing the IP can disconnect SSH. Ask for a suggestion, then allocate automatically or specify an address:

   ```bash
   bin/bootstrap-nixos-vm --suggest-ip

   bin/bootstrap-nixos-vm my-service \
     --static-ip auto --description "My service"
   ```

   Replace `auto` with a CIDR such as `192.168.1.210/24` to select it yourself. For this LAN, gateway `192.168.1.1` and DNS `192.168.1.169` default from the inventory; override them with `--gateway` and repeatable `--dns` flags. Other subnets require explicit gateway and DNS values. The interface is detected from the default route or a sole non-loopback interface; use `--interface ens18` when ambiguous. Static configuration has automated checks, but a live static-network trial remains pending.

   With no arguments at a terminal, the script prompts for hostname and static IP (default `auto`; enter `dhcp` to keep DHCP). Supplying a hostname without `--static-ip` preserves DHCP, including for local NAT tests. The `headless` profile is the only supported profile. Bootstrap detects boot firmware and hardware, creates host and home modules, stages them together with a static allocation when applicable, and runs the first rebuild.
5. Check root growth with `lsblk` and `df -h /`. Edit `hosts/<hostname>/configuration.nix`, then run `sudo nixos-rebuild switch --flake .#<hostname>` from the repo. Test a small package or service change and confirm SSH and console recovery still work.
6. Review `git diff --cached`, commit the new host and subsequent changes, and push manually when ready. Scripts never commit or push.

Bootstrap requires a clean checkout and normally fetches and updates with fast-forward-only Git operations. Local unpushed commits are preserved. If the remote and local histories diverge, reconcile them deliberately; local work is never reset. `--skip-update` uses the current clean snapshot for local tests or offline work. `--no-switch` creates and stages configuration for review without applying it. If a rebuild fails, fix the staged files and rerun the printed rebuild command; rerunning bootstrap with the same hostname is intentionally rejected.

## LAN address inventory

[network.json](network.json) records the LAN subnet, DHCP/static ranges, gateway, DNS server, and known address allocations. Its `machines` array contains an `ip`, `hostname`, and `comment` for each entry. Keep the JSON human-readable with two-space indentation and a trailing newline; bootstrap preserves that formatting when writing it. UniFi DHCP uses `192.168.1.2`–`192.168.1.200`; new static VM addresses must use `.201`–`.254`. Initially recorded addresses are:

| Address | Purpose |
| --- | --- |
| `192.168.1.1` | UniFi gateway |
| `192.168.1.169` | Raspberry Pi Pi-hole DNS |
| `192.168.1.201` | TrueNAS VM |
| `192.168.1.209` | iMessage Mac Mini server |
| `192.168.1.250` | Proxmox host |

The inventory labels describe existing devices; they do not establish DNS records. `--suggest-ip` reads the local inventory without fetching, reserving, or changing anything; the initial suggestion is `192.168.1.202/24`. `--static-ip auto` selects an unallocated address during bootstrap. Duplicate known addresses are rejected before generating a host, and the new allocation is staged with its configuration, including with `--no-switch`.

An unallocated address in this file is not proof that the LAN address is unused. Add other manually configured devices to the inventory, and keep it current when changing or retiring a host. The script does not query UniFi or act as a central allocator. Two stale or concurrent checkouts can select the same address: provision VMs sequentially, review and commit each allocation, then push it manually before provisioning from another checkout. Leave normal bootstrap synchronization enabled for real provisioning; `--skip-update` can use stale assignments. After editing an existing VM's address, update both its Nix configuration and the inventory in the same change. DNS records remain a separate Pi-hole task.

SSH password login is disabled. For recovery, use the VM console with `dbalatero` and the password stored in 1Password. The password and GitHub private key are shared by all clones. Rotate existing VMs individually when replacing either credential; rebuilding a template does not update existing clones.
