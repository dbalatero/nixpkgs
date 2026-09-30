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
    # Nested virtualization has not been verified on this guest.
    system-features = lib.mkForce ["benchmark" "big-parallel"];
  };
  # Cache outputs are not roots. Keep GC off until retention is implemented.
  nix.gc.automatic = false;
  services.fstrim.enable = true;
}
