# Media stack and Immich
{pkgs, ...}: {
  imports = [
    ./hardware-configuration.nix
    ../common/nixos-vm
    ../common/nfs
    ./import-stack.nix
    ./prowlarr.nix
    ./seerr.nix
    ./plex.nix
    ./bazarr.nix
    ./sabnzbd.nix
    ./qbittorrent.nix
    ./ebook-import.nix
    ./calibre-web-automated.nix
  ];

  networking.hostName = "media";
  # Firmware and VA-API userspace support for the passed-through Intel Arc A380.
  hardware.enableRedistributableFirmware = true;
  hardware.graphics = {
    enable = true;
    extraPackages = [pkgs.intel-media-driver];
  };
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = false;
  boot.loader.efi.efiSysMountPoint = "/boot";

  networking.useDHCP = false;
  networking.interfaces."ens18" = {
    useDHCP = false;
    ipv4.addresses = [{ address = "192.168.1.205"; prefixLength = 24; }];
  };
  networking.defaultGateway = { address = "192.168.1.1"; interface = "ens18"; };
  networking.nameservers = ["192.168.1.202"];
}
