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

  networking.nameservers = ["1.1.1.1" "8.8.8.8"];

  services.tailscale = {
    enable = true;
    openFirewall = true;
    useRoutingFeatures = "server";
    extraSetFlags = [
      "--advertise-routes=${network.subnet}"
      "--accept-dns=false"
      "--accept-routes=false"
      "--snat-subnet-routes=true"
    ];
    # Keep logs in the bounded journal configured in pihole.nix; disabling
    # upstream debug logging also disables its on-disk upload buffer.
    disableUpstreamLogging = true;
  };

  # Tailscale traffic may have an asymmetric return path.
  networking.firewall.checkReversePath = "loose";

  # Route private lookups to FTL while public lookups remain independent of it.
  # Keep the shared search suffix on this link, not on the public DNS servers.
  services.resolved.settings.Resolve.Domains = lib.mkForce [];
  systemd.network.networks."40-ens18" = {
    dns = [network.machinesByName.${config.networking.hostName}.ip];
    domains = config.networking.search ++ ["~${network.domain}"];
    networkConfig.DNSDefaultRoute = false;
  };
}
