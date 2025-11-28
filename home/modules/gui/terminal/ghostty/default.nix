{
  config,
  pkgs,
  lib,
  ...
}: {
  programs.ghostty = {
    enable = true;

    # On macOS, we install via homebrew cask, so don't install via nix
    # On Linux, install from nixpkgs
    package =
      if pkgs.stdenv.isDarwin
      then null
      else pkgs.ghostty;

    settings = {
      # Basic settings - customize as needed
      font-family = "JetBrainsMono Nerd Font";
      font-size = 13;

      # Performance
      window-padding-x = 10;
      window-padding-y = 10;

      # Behavior
      confirm-close-surface = false;
      quit-after-last-window-closed = true;
    };
  };
}
