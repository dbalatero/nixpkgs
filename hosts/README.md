# NixOS Hosts Configuration

This directory contains NixOS system configurations for all managed hosts.

## Directory Structure

```
hosts/
├── common/                 # Shared configuration modules
│   ├── nixos/             # Base NixOS config (SSH, users, packages)
│   │   ├── ssh.nix        # Hardened SSH configuration
│   │   ├── users.nix      # User accounts and sudo config
│   │   ├── packages.nix   # Base system packages
│   │   └── default.nix    # Imports all common modules
│   └── desktop/           # Desktop environment config (optional)
│       └── default.nix    # KDE Plasma, gaming, audio, etc.
├── template/              # Template for new hosts
│   ├── configuration.nix
│   └── hardware-configuration.nix.example
├── panther/               # Example: Gaming desktop
└── <hostname>/            # Your hosts
```

## Shared Configuration

All NixOS hosts automatically include:

### From `common/nixos/`:
- **SSH**: Hardened sshd config (based on [dev-sec.io recommendations](https://dev-sec.io/baselines/ssh/))
  - Key-only authentication
  - Strong cryptography
  - Session timeouts
  - Verbose logging
- **User**: `dbalatero` account with sudo access (no password required)
- **Base packages**: git, vim, neovim, wget, net-tools
- **Kernel**: Latest Linux kernel
- **Network**: NetworkManager enabled
- **Locale**: en_US.UTF-8
- **Timezone**: America/New_York (can be overridden per-host)

### From `common/desktop/` (optional):
- KDE Plasma 6 desktop environment
- Steam with Proton-GE
- Gaming tools (GameMode, MangoHud, Lutris, Bottles, Heroic)
- Audio (PipeWire)
- Fonts (Noto, Liberation, DejaVu, etc.)
- Performance tuning (CPU governor, keyd for keyboard remapping)

## Adding a New Host

### Step 1: Copy the Template

```bash
# Replace HOSTNAME with your actual hostname
cp -r hosts/template hosts/HOSTNAME
```

### Step 2: Generate Hardware Configuration

On the new machine (from a NixOS installer or existing system):

```bash
# Generate hardware config
nixos-generate-config --show-hardware-config > /tmp/hardware-configuration.nix

# Copy it to your config repo
cp /tmp/hardware-configuration.nix ~/.config/nixpkgs/hosts/HOSTNAME/
```

Or if generating remotely:

```bash
ssh root@NEW_HOST "nixos-generate-config --show-hardware-config" > hosts/HOSTNAME/hardware-configuration.nix
```

### Step 3: Customize configuration.nix

Edit `hosts/HOSTNAME/configuration.nix`:

1. **Update the hostname**:
   ```nix
   networking.hostName = "HOSTNAME";  # Change this!
   ```

2. **Add description** at the top:
   ```nix
   # HOSTNAME - Production web server (or whatever this host is)
   ```

3. **Choose configuration type**:

   **For headless servers** (default):
   ```nix
   imports = [
     ./hardware-configuration.nix
     ../common/nixos
   ];
   ```

   **For desktop machines**:
   ```nix
   imports = [
     ./hardware-configuration.nix
     ../common/nixos
     ../common/desktop  # Add this line
   ];
   ```

4. **Customize boot loader** if needed (the template uses GRUB UEFI by default)

5. **Override timezone** if needed:
   ```nix
   time.timeZone = "America/Los_Angeles";
   ```

6. **Add host-specific packages**:
   ```nix
   environment.systemPackages = with pkgs; [
     docker
     postgresql
     # etc.
   ];
   ```

### Step 4: Add to flake.nix

Edit `flake.nix` and add a new `nixosConfigurations` entry:

```nix
nixosConfigurations.HOSTNAME = nixpkgs.lib.nixosSystem {
  system = "x86_64-linux";  # or "aarch64-linux" for ARM
  modules = [
    ./hosts/HOSTNAME/configuration.nix
    ./hosts/HOSTNAME/hardware-configuration.nix
    home-manager.nixosModules.home-manager
    {
      nixpkgs.config.allowUnfree = true;

      home-manager.users.dbalatero = {
        imports = [
          ./home/hosts/HOSTNAME  # Create this for home-manager config
          nixvim.homeModules.nixvim
          stylix.homeModules.stylix
          # plasma-manager.homeModules.plasma-manager  # Only for desktop hosts
        ];
      };

      home-manager.useGlobalPkgs = true;
      home-manager.extraSpecialArgs = {inherit inputs;};
    }
  ];
};
```

### Step 5: Create Home-Manager Config

Create the corresponding home-manager config:

```bash
mkdir -p home/hosts/HOSTNAME
```

Create `home/hosts/HOSTNAME/default.nix`:

**For headless servers**:
```nix
{
  ...
}: {
  imports = [
    ../../modules/default.nix
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";
}
```

**For desktop machines**:
```nix
{
  ...
}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui/nixos
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";
}
```

### Step 6: Stage New Files

Since this is a Nix flake, you must stage new files for Git:

```bash
git add hosts/HOSTNAME/
git add home/hosts/HOSTNAME/
```

### Step 7: Deploy

On the new machine:

```bash
# Initial deploy (from this repo directory)
sudo nixos-rebuild switch --flake .#HOSTNAME

# Or remotely (if SSH is already configured)
nixos-rebuild switch --flake .#HOSTNAME --target-host root@HOSTNAME --build-host localhost
```

## Examples

### Headless Server Example

```nix
# hosts/webserver/configuration.nix
# webserver - Production Nginx server
{
  config,
  lib,
  pkgs,
  ...
}: {
  imports = [
    ./hardware-configuration.nix
    ../common/nixos
  ];

  networking.hostName = "webserver";

  boot.loader.grub.device = "/dev/sda";  # BIOS mode

  services.nginx.enable = true;
  networking.firewall.allowedTCPPorts = [ 80 443 ];
}
```

### Desktop Example

See `hosts/panther/configuration.nix` for a complete desktop example with AMD GPU configuration.

## Modifying Shared Configuration

### Updating SSH Settings

Edit `hosts/common/nixos/ssh.nix` - changes apply to all hosts on next rebuild.

### Updating User Configuration

Edit `hosts/common/nixos/users.nix` - affects all hosts.

### Updating Base Packages

Edit `hosts/common/nixos/packages.nix` - adds packages to all hosts.

### Updating Desktop Settings

Edit `hosts/common/desktop/default.nix` - affects only desktop hosts.

## Tips

- **Keep host configs minimal**: Most config should be in `common/`
- **Use `lib.mkDefault`** in common configs for values that hosts might override
- **Document host-specific settings** with comments
- **Test changes** on a non-critical host first
- **Stage files for Git** before building (flakes requirement)
