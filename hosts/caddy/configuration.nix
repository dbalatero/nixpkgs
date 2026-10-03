# NixOS homelab VM
{config, lib, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
in {
  imports = [
    ./hardware-configuration.nix
    ../common/nixos-vm
    ./caddy.nix
    ./homepage.nix
    ./authentik.nix
  ];

  networking.hostName = "caddy";
  users.users.dbalatero.openssh.authorizedKeys.keyFiles = [../builder/admin-key.pub];
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = false;
  boot.loader.efi.efiSysMountPoint = "/boot";

  networking.useDHCP = false;
  networking.interfaces."ens18" = {
    useDHCP = false;
    ipv4.addresses = [
      {
        address = network.machinesByName.${config.networking.hostName}.ip;
        prefixLength = network.prefixLength;
      }
    ];
  };
  networking.defaultGateway = {
    address = network.gateway;
    interface = "ens18";
  };
  networking.nameservers = network.dns;
}
