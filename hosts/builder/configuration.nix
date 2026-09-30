# NixOS homelab VM
{...}: {
  imports = [
    ./hardware-configuration.nix
    ../common/nixos-vm
    ./builder.nix
    ./cache.nix
    ./logging.nix
  ];

  networking.hostName = "builder";
  programs.ssh.knownHosts.caddy = {
    hostNames = ["caddy" "caddy.vm.netcat.cloud" "192.168.1.203"];
    publicKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPWY0W949me7nnQQRS66jPAVWnKrNhgpZXT1Tq/n4V7o";
  };
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = false;
  boot.loader.efi.efiSysMountPoint = "/boot";

  networking.useDHCP = false;
  networking.interfaces."ens18" = {
    useDHCP = false;
    ipv4.addresses = [{ address = "192.168.1.204"; prefixLength = 24; }];
  };
  networking.defaultGateway = { address = "192.168.1.1"; interface = "ens18"; };
  networking.nameservers = ["192.168.1.202"];
}
