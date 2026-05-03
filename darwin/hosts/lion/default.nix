{lib, ...}: {
  imports = [
    ../common.nix
  ];

  # Remove volumehud - requires macOS 26 (Tahoe)
  homebrew.casks = lib.mkForce (
    lib.filter (cask: cask != "volumehud")
      (import ../common.nix {inherit lib;}).homebrew.casks
  );
}
