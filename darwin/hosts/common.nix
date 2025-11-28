{ config, pkgs, ... }:

{
  nix.enable = false;

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # Primary user for system defaults
  system.primaryUser = "dbalatero";

  system.defaults = {
    dock.autohide = true;
    finder.AppleShowAllExtensions = true;
    NSGlobalDomain.AppleShowAllExtensions = true;
  };

  # Enable sudo with Touch ID
  security.pam.services.sudo_local.touchIdAuth = true;

  # Necessary for using flakes on this system
  nix.settings.experimental-features = "nix-command flakes";

  # Set Git commit hash for darwin-version
  system.configurationRevision = null;

  # Used for backwards compatibility
  system.stateVersion = 5;

  # The platform the configuration will be used on
  nixpkgs.hostPlatform = "aarch64-darwin"; # or "x86_64-darwin"
}