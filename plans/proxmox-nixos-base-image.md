# Proxmox NixOS Base Image Plan

## Goal

Create an x86_64 Linux `qcow2` base image for Proxmox. It boots headless NixOS, has this repo cloned at `/home/dbalatero/.config/nixpkgs`, accepts the laptop and desktop SSH public keys for login, has a shared console recovery password chosen during image preparation, and contains a shared GitHub SSH write key for repo push/pull.

Develop and evaluate the configuration on the macOS M1 Air. Build and boot the image on the AMD NixOS desktop, then import it into Proxmox and convert it to a VM template.

**First-login success:** after cloning the template, SSH in as `dbalatero`, open the existing writable repo, run one bootstrap command to name and configure that VM, edit its NixOS configuration, rebuild locally, then commit and push to GitHub. No separate installation, manual repo clone, or hand-edited system file should be needed.

Keep `lab/README.md` as the short operator guide for creating a VM. Update it when each phase supplies a tested command or decision; keep implementation details and exhaustive checks in this plan.

## Design decisions

- Use the NixOS `qcow` image variant for x86_64 Linux. Author and evaluate on the M1 Mac; build and test on the AMD NixOS desktop.
- Embed the laptop and desktop SSH public keys for `dbalatero`. Disable SSH password login; allow passwordless `sudo`. Prompt for a long, unique console recovery password during each image build, after the Nix build succeeds. Create it in 1Password the first time, then paste the same password on later builds. Console recovery requires access to the VM console.
- Inject a salted password hash and a shared, write-capable GitHub SSH private key only after the Nix build. Neither secret enters Git, command arguments, logs, or the Nix store. Every clone intentionally shares them. A new template does not rotate existing clones; rotate each VM when needed.
- Use `~/code/proxmox-base` on the AMD desktop for user-managed artifacts. Nix keeps the secret-free build output in `/nix/store`; copy it into this workspace before adding secrets. The build script sets `umask 077`, creates or fixes the workspace to `0700`, and allows an explicit work-directory override. Directories and executable helpers are `0700`, finished images `0400`, and writable test copies or temporary files `0600`.
- Keep the prepared template image unbooted. Boot only disposable copies so cloned VMs generate their own machine identity and SSH host keys.
- Scripts may stage host files and print next commands, but commits and pushes remain manual.

## Disk sizing

- Give the template a modest minimum virtual disk size with enough free space for a NixOS rebuild; start with 20 GiB and adjust after the desktop smoke test. Every clone starts at least this large. A larger virtual disk does not immediately consume that much physical storage on thin-provisioned Proxmox storage, but actual usage must still be monitored.
- For a VM that needs more space, resize that clone's disk in Proxmox before its first boot. Keep the template size unchanged. Make sure the image enables root partition growth (`boot.growPartition`) and root filesystem growth (`fileSystems."/".autoResize`); verify both with `lsblk` and `df -h /` after boot.
- Growing a disk later follows the same pattern: enlarge it in Proxmox, reboot the guest if needed, and verify partition and filesystem sizes. Do not rely on shrinking a clone back below the template size. Consider a separately configured data disk for services whose data needs independent sizing.

## Phase 1: Work on the macOS M1 Air

This phase produces reviewable code and checks it without building or booting a Linux image.

### 1. Define the base image

- [~] Add `nixosConfigurations.proxmox-base` to `flake.nix`, using `system = "x86_64-linux"` and a dedicated module under `hosts/proxmox-base/`.
- [ ] Configure a headless guest with DHCP, SSH, QEMU guest agent, and `dbalatero` in `wheel`. First login must already provide Nix flakes, `nixos-rebuild`, `nixos-generate-config`, `sudo`, an editor, Git, and bootstrap dependencies.
- [ ] Confirm the selected `qcow` image layout has a growable root partition and filesystem; set `boot.growPartition` and `fileSystems."/".autoResize` if the image module does not already provide them.
- [ ] Remove or override `hosts/common/nixos/users.nix`'s `initialPassword = "changeme"` for this image and its generated VM hosts. Keep the user in `wheel` with passwordless `sudo`. Configure the user to load a root-only password hash file from the guest filesystem, outside the Nix store, so the console password survives rebuilds.
- [~] Add the laptop and desktop SSH login public keys for `dbalatero`; verify both fingerprints and that only `.pub` files are tracked.
- [~] Add ignored paths for image-only private key material. Keep the actual GitHub private key outside the Nix expression and all Nix build inputs.
- [ ] Update `lab/README.md` with the confirmed login prerequisites, template disk minimum, and console recovery method.

### 2. Write the image scripts

- [ ] Add `bin/build-proxmox-base-image` as the sole user-facing entry point. Build `.#proxmox-base` as a `qcow` image, copy the secret-free result into the workspace, then prompt twice with hidden input for the recovery password. Produce a separate prepared qcow2 with a 20 GiB minimum virtual size and print only its path as the import artifact. Never report a partial image as ready.
- [ ] In the build script or an internal preparation helper, hash the entered password and inject its hash into a root-only guest file. Inject the ignored local `~/.ssh/id_github`, a verified GitHub `known_hosts` entry, and a real writable clone of `git@github.com:dbalatero/nixpkgs.git` at `/home/dbalatero/.config/nixpkgs`. Preserve `.git`, set correct ownership and permissions, set `origin` and an upstream branch, and ensure Git name/email and SSH identity work on first login.
- [ ] Validate input images, private key, workspace ownership, and required Linux image tools before making a final image. Pass secrets only through protected pipes or file descriptors, never arguments or environment variables. Keep any required temporary files `0600` inside the workspace and remove them on success or failure; finish images as `0400`. Keep boot-test copies `0600`, avoid overwriting an existing prepared image, and do not modify the import artifact.
- [ ] Update the README with the build command, the password prompt, and the final artifact location once the script interface is fixed.

### 3. Write the cloned VM bootstrap script

- [ ] Add `bin/bootstrap-nixos-vm <hostname>` with flags for description, static IP, gateway, DNS, and profile. Document the expected values and defaults.
- [ ] Have it generate hardware configuration on the cloned VM, create `hosts/<hostname>` and `home/hosts/<hostname>`, add `nixosConfigurations.<hostname>` to `flake.nix`, and stage the new files.
- [ ] Validate arguments and existing-host collisions before changing files. Print the changes and the manual commit commands, then run `sudo nixos-rebuild switch --flake .#<hostname>`.
- [ ] Before editing, fetch the latest repo state with a fast-forward-only update when the checkout is clean. Explain how to recover if the VM was cloned from an older template or the working tree has changes; never discard local work.
- [ ] Generate VM networking and bootloader settings for the actual Proxmox hardware. Do not copy the current template's hardcoded `eth0` or `/dev/sda` assumptions. Keep DHCP as the safe default; validate optional static IP, gateway, and DNS settings before switching.
- [ ] Preserve the working Git checkout and SSH key across the first rebuild. Verify that the new host module includes the needed user, SSH, Git, editor, sudo, and home-manager setup.
- [ ] Update the README with the bootstrap command's actual flags and defaults, the edit/rebuild path, and the manual commit/push step.

### 4. Check what can be checked on the Mac

- [ ] Stage newly created Nix files with `git add` so flake evaluation includes them; do not commit automatically.
- [ ] Parse changed Nix files with `nix-instantiate --parse <file> >/dev/null` and shell scripts with `bash -n <script>`; run `shellcheck` if available.
- [ ] Evaluate the image derivation without building it, for example `nix eval --raw .#nixosConfigurations.proxmox-base.config.system.build.images.qcow.drvPath`. Fix option errors revealed by evaluation.
- [ ] Confirm the password hash file is read from the guest filesystem during activation, not during the Nix build; validate that the chosen user-management mode accepts it.
- [ ] Exercise script help, argument validation, and safe failure paths with disposable inputs. Do not put the real GitHub private key into a test fixture.
- [ ] Keep untested steps in the README marked as planned. Record detailed Linux test and Proxmox import commands here until they have been run.
- [ ] Review the staged changes, then commit and push them manually so the AMD desktop can pull the same revision. Never include the private key in this transfer.

**Mac handoff:** tracked configuration and scripts have passed parsing, evaluation, and script checks; the reviewed commit is available to the AMD desktop; the real private key remains outside Git and the Nix store. Any Linux-only checks are listed for Phase 2.

## Phase 2: AMD NixOS desktop

- [ ] Pull the reviewed commit from the Mac and run `bin/build-proxmox-base-image` with the local ignored GitHub key. Create the recovery password in 1Password or paste the existing one when prompted. Keep the secret-free raw image for repeatable preparation.
- [ ] Confirm `~/code/proxmox-base` and any subdirectories are `0700`, finished images are `0400`, and any writable test copies are `0600`. Confirm no secret-bearing artifacts or temporary files are left outside that workspace.
- [ ] Boot a `0600` copy of the prepared qcow2 under QEMU with SSH port forwarding. Verify DHCP, guest agent, desktop-key login, rejected SSH password login, passwordless `sudo`, and console login with the recovery password. Confirm the laptop public key is embedded; test login with the laptop's private key from the laptop when the VM is reachable.
- [ ] Verify the prepared image grows its root partition and filesystem to the 20 GiB virtual size on boot, and that a NixOS rebuild has adequate free space.
- [ ] At first login, verify the writable repo and its SSH `origin`, Git author settings, editor, flake evaluation, and `sudo nixos-rebuild` are available without installation. Verify `ssh -T git@github.com` authenticates with `~/.ssh/id_github`.
- [ ] Confirm neither the private key nor password hash entered Git or the Nix store; keep all secret-bearing image copies private.
- [ ] Replace the README's planned desktop steps with the build command, output location, and brief QEMU smoke-test steps that actually worked.

## Phase 3: Proxmox template and first clone

- [ ] Import the prepared, never-booted qcow2 into Proxmox. Set a compatible firmware mode and disk bus, enable the guest agent, and convert it directly to a template. Boot a clone for testing, never the template source disk.
- [ ] Resize the first clone's disk in Proxmox before booting it, choosing a size larger than the template. Verify the guest sees the larger root partition and filesystem with `lsblk` and `df -h /`; keep smaller service VMs at the template size.
- [ ] Clone the template and run `bin/bootstrap-nixos-vm <hostname> ...` with that VM's description, networking, and profile values.
- [ ] Confirm the clone has its own machine ID and SSH host keys. Confirm generated hardware configuration, host and home modules, flake entry, staged files, networking, and `nixos-rebuild switch` all succeed.
- [ ] Confirm key-only SSH login, passwordless `sudo`, and console password login still work after the clone's first `nixos-rebuild switch`. Test console login without relying on SSH so it is a real recovery path.
- [ ] Add a small package or service to the new host configuration, rebuild again, and verify it works. This proves the normal edit-and-rebuild loop beyond the bootstrap itself.
- [ ] Review, commit, and push from the VM manually to confirm GitHub write access.
- [ ] Replace the README's planned Proxmox and bootstrap steps with the verified clone, disk resize, login, bootstrap, rebuild, and recovery steps; remove its work-in-progress notice only after following it end to end.
- [ ] Record any desktop or Proxmox fixes in this plan and the scripts so the next clone follows the same procedure.
