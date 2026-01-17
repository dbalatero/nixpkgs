{
  config,
  lib,
  pkgs,
  ...
}: {
  imports = [
    ./ssh.nix
    ./users.nix
    ./packages.nix
  ];

  # Use latest kernel
  boot.kernelPackages = pkgs.linuxPackages_latest;

  # Configure network connections with NetworkManager
  networking.networkmanager.enable = true;

  # Default timezone (can be overridden per-host)
  time.timeZone = lib.mkDefault "America/New_York";

  # Internationalization
  i18n.defaultLocale = "en_US.UTF-8";
  i18n.extraLocaleSettings = {
    LC_ADDRESS = "en_US.UTF-8";
    LC_IDENTIFICATION = "en_US.UTF-8";
    LC_MEASUREMENT = "en_US.UTF-8";
    LC_MONETARY = "en_US.UTF-8";
    LC_NAME = "en_US.UTF-8";
    LC_NUMERIC = "en_US.UTF-8";
    LC_PAPER = "en_US.UTF-8";
    LC_TELEPHONE = "en_US.UTF-8";
    LC_TIME = "en_US.UTF-8";
  };

  # NixOS state version
  system.stateVersion = "25.11";
}
