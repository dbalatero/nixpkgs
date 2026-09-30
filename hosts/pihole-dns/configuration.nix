# NixOS homelab VM
{config, lib, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
in {
  imports = [
    ./hardware-configuration.nix
    ../common/nixos-vm
    ./pihole.nix
  ];

  networking.hostName = "pihole-dns";
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

  networking.nameservers = ["1.1.1.1" "8.8.8.8"];

  # Route private lookups to FTL while public lookups remain independent of it.
  # Keep the shared search suffix on this link, not on the public DNS servers.
  services.resolved.settings.Resolve.Domains = lib.mkForce [];
  systemd.network.networks."40-ens18" = {
    dns = [network.machinesByName.${config.networking.hostName}.ip];
    domains = config.networking.search ++ ["~${network.domain}"];
    networkConfig.DNSDefaultRoute = false;
  };
}
