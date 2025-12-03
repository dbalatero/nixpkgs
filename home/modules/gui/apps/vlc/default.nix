{pkgs, ...}: {
  # On macOS, we install via homebrew cask, so don't install via nix
  # On Linux, install from nixpkgs
  home.packages =
    if pkgs.stdenv.isDarwin
    then []
    else [pkgs.vlc];
}
