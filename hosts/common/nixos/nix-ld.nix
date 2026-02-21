{
  config,
  lib,
  pkgs,
  ...
}: {
  # Enable nix-ld to run prebuilt binaries on NixOS.
  # Without this, dynamically linked binaries from outside nixpkgs
  # (e.g. mise-managed runtimes, npm native modules, VS Code extensions)
  # fail because NixOS lacks the standard /lib/ld-linux dynamic linker.
  programs.nix-ld = {
    enable = true;
    libraries = with pkgs; [
      stdenv.cc.cc
      zlib
      zstd
      openssl
      curl
      libffi
      readline
      bzip2
      ncurses
      sqlite
      xz
      libyaml
      gdbm
      icu
    ];
  };
}
