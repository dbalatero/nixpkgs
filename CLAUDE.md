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

```
home/
├── hosts/           # Host-specific configurations
│   └── {hostname}/  # Each hostname has its own directory
│       └── default.nix  # Imports shared modules
└── modules/         # Shared home-manager modules
    └── cli/         # CLI-related modules
        ├── core/    # Core CLI tools (fd, ripgrep, wget, etc.)
        └── claude/  # Claude Code installation
```

### Module System

The configuration uses a hierarchical import system:
1. `flake.nix` references a host configuration in `home/hosts/{hostname}/default.nix`
2. Host configuration imports `home/modules/default.nix`
3. `home/modules/default.nix` sets base home-manager settings and imports category modules
4. Category modules (e.g., `cli/default.nix`) import specific feature modules

All modules are auto-imported through their respective `default.nix` files. To add a new module, create the directory and add it to the appropriate `imports` list.

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

### Add New Packages

Add packages to the appropriate module in `home/modules/`. For CLI tools, add them to `home/modules/cli/core/default.nix` or create a new module directory under `home/modules/cli/`.

## Configuration Details

- Home state version: 25.05
- Unfree packages are allowed (`nixpkgs.config.allowUnfree = true`)
- Base username: `dbalatero`
- Home directory: `/home/dbalatero`
