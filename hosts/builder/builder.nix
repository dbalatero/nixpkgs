{config, lib, pkgs, ...}: let
  keyDirectory = ./client-keys;
  keys = builtins.readDir keyDirectory;
  keyNames = builtins.filter (name: keys.${name} == "regular" && lib.hasSuffix ".pub" name) (builtins.attrNames keys);
in {
  users.groups.remotebuild = {};
  users.users.remotebuild = {
    isSystemUser = true;
    group = "remotebuild";
    shell = pkgs.bash;
    openssh.authorizedKeys.keys = map (name:
      "restrict " + lib.trim (builtins.readFile (keyDirectory + "/${name}"))) keyNames;
  };
  services.openssh.extraConfig = ''
    Match User remotebuild
      ForceCommand ${config.nix.package}/bin/nix-daemon --stdio
      AllowTcpForwarding no
      AllowAgentForwarding no
      PermitTTY no
    Match all
  '';
  nix.settings = {
    trusted-users = ["root" "remotebuild"];
    max-jobs = 2;
    cores = 4;
    # Reclaim unused store paths during builds before the 100 GiB disk fills.
    min-free = 10 * 1024 * 1024 * 1024;
    max-free = 20 * 1024 * 1024 * 1024;
    # Nested virtualization has not been verified on this guest.
    system-features = lib.mkForce ["benchmark" "big-parallel"];
  };
  # max-jobs applies per connected Nix worker; build-user locks are shared
  # across clients. Two sandbox identities bound ordinary builds fleet-wide.
  nix.nrBuildUsers = 2;
  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 14d";
  };
  services.fstrim.enable = true;
}
