{config, lib, ...}: let
  network = import ../../../lab/network.nix {inherit lib;};
in {
  # The base image and non-lab VMs must not inherit the lab's search domain.
  networking.search = lib.mkIf (builtins.hasAttr config.networking.hostName network.machinesByName)
    (lib.mkAfter [network.machineDomain]);
}
