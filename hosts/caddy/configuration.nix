# NixOS homelab VM
{...}: {
  imports = [
    ./hardware-configuration.nix
    ../common/nixos-vm
  ];

  networking.hostName = "caddy";
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = false;
  boot.loader.efi.efiSysMountPoint = "/boot";

  networking.useDHCP = false;
  networking.interfaces."ens18" = {
    useDHCP = false;
    ipv4.addresses = [{ address = "192.168.1.203"; prefixLength = 24; }];
  };
  networking.defaultGateway = { address = "192.168.1.1"; interface = "ens18"; };
  networking.nameservers = ["192.168.1.202"];
}
