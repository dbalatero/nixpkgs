# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Nix flake-based home-manager configuration monorepo for system configurations. It uses home-manager to manage user environments across different hosts.

## Architecture

### Flake Structure

The repository is organized around a Nix flake (`flake.nix`) that:
- Uses `nixpkgs-unstable` as the base nixpkgs input
- Integrates with home-manager for user environment management
- Defines homeConfigurations for each host (e.g., `racknerd-a61953`)

### Directory Structure

The repository supports different machine types:
- **Headless servers** - terminal-based development environment only
- **Linux desktops** - GUI apps and terminal emulators for Linux
- **macOS desktops** - GUI apps and terminal emulators for macOS

```
home/
├── hosts/           # Host-specific configurations
│   └── {hostname}/  # Each hostname has its own directory
│       └── default.nix  # Imports shared modules
└── modules/         # Shared home-manager modules
    ├── core/                    # Base home-manager settings
    │   └── default.nix          # Username, stateVersion, allowUnfree, etc.
    │
    ├── pde/                     # Personal Development Environment (terminal-based)
    │   ├── core/                # CLI tools (fd, ripgrep, wget, etc.)
    │   ├── claude/              # Claude Code installation
    │   ├── neovim/              # Neovim configurations
    │   ├── shell/               # Shell configs (bash, zsh, fish)
    │   ├── git/                 # Git configuration
    │   ├── tmux/                # Terminal multiplexer
    │   ├── stylix/              # Terminal theming
    │   └── default.nix          # Imports all PDE modules
    │
    ├── gui/                     # GUI-related modules (only created when needed)
    │   ├── terminal/            # Terminal emulators (only on GUI machines)
    │   │   ├── ghostty/
    │   │   ├── alacritty/
    │   │   └── default.nix
    │   │
    │   ├── apps/                # GUI applications
    │   │   ├── common/          # Cross-platform desktop apps
    │   │   ├── linux/           # Linux desktop apps (firefox, etc.)
    │   │   ├── darwin/          # macOS apps (use homebrew casks)
    │   │   └── default.nix
    │   │
    │   └── default.nix
    │
    └── platform/                # Platform-specific system configs (only created when needed)
        ├── linux/               # Linux-specific settings
        ├── darwin/              # macOS-specific settings
        └── default.nix
```

### Module System

The configuration uses a hierarchical import system:
1. `flake.nix` references a host configuration in `home/hosts/{hostname}/default.nix`
2. Host configuration imports `home/modules/default.nix`
3. `home/modules/default.nix` imports `core` and `pde` (and optionally `gui`, `platform`)
4. Category modules import specific feature modules

All modules are auto-imported through their respective `default.nix` files.

#### Module Composition by Host Type

**Headless Servers** - Minimal configuration with just terminal tools:
```nix
imports = [
  ../../modules/core
  ../../modules/pde
];
```

**Linux Desktop** - Full GUI environment with Linux-specific apps:
```nix
imports = [
  ../../modules/core
  ../../modules/pde
  ../../modules/gui/terminal
  ../../modules/gui/apps/common
  ../../modules/gui/apps/linux
  ../../modules/platform/linux
];
```

**macOS Desktop** - Full GUI environment with macOS-specific apps:
```nix
imports = [
  ../../modules/core
  ../../modules/pde
  ../../modules/gui/terminal
  ../../modules/gui/apps/common
  ../../modules/gui/apps/darwin
  ../../modules/platform/darwin
];
```

#### Principles
- **PDE is self-contained** - All terminal-based development tools go here
- **GUI is optional** - Headless servers don't need any GUI modules
- **Platform-specific separation** - Linux and macOS apps are kept separate
- **Composable** - Hosts can mix and match what they need
- **Don't create empty directories** - Only create module folders when you have content for them

## Common Commands

### Initial Setup
```bash
./bin/setup
```
Installs Nix (if not present) and runs the initial home-manager switch.

### Apply Configuration Changes
```bash
./bin/switch
```
Applies the home-manager configuration for the current hostname. The script automatically detects the hostname and uses either `home-manager` (if installed) or `nix run home-manager/master`.

**IMPORTANT**:
- On **NixOS machines** (where system configuration is managed via NixOS): You CAN run `./bin/switch` automatically as it may require sudo for system-level changes.
- On **non-NixOS machines** (macOS, or Linux machines using only home-manager): DO NOT run `./bin/switch` automatically. The user will run this command themselves. After making configuration changes, inform the user to run `./bin/switch` to apply them.

### Git Workflow for Nix Configuration Changes

**NEVER create commits automatically.** When making Nix configuration changes:
1. Use `git add` to stage new files and directories (required for flakes to see them)
2. Let the user review and commit changes themselves

Example:
```bash
# After creating new Nix modules
git add home/modules/gui/nixos/mangohud/
git add home/modules/gui/nixos/default.nix
# User will commit when ready
```

### Add a New Host

1. Create a new directory: `home/hosts/{hostname}/`
2. Create `home/hosts/{hostname}/default.nix` that imports `../../modules/default.nix`
3. Add the homeConfiguration to `flake.nix`:
```nix
homeConfigurations."{hostname}" = home-manager.lib.homeManagerConfiguration {
  pkgs = nixpkgs.legacyPackages.{architecture};
  modules = [
    ./home/hosts/{hostname}
  ];
};
```

### Add New Modules

1. Create a new directory under the appropriate category
2. Add a `default.nix` file in that directory
3. Import the new module in the parent category's `default.nix`

For example, to add a new PDE tool:
```bash
mkdir -p home/modules/pde/fzf
# Create home/modules/pde/fzf/default.nix
# Add ./fzf to imports in home/modules/pde/default.nix
```

For CLI packages, add them to `home/modules/pde/core/default.nix` or create a new module as shown above.

## Configuration Details

- Home state version: 25.05
- Unfree packages are allowed (`nixpkgs.config.allowUnfree = true`)
- Base username: `dbalatero`
- Home directory: `/home/dbalatero`

## Desktop Environment

- **Window Manager/Desktop**: KDE Plasma (not Hyprland)
- Gaming configurations (Steam, etc.) should be configured for KDE Plasma window rules
