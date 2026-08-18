{
  lib,
  pkgs,
  ...
}: {
  home.packages = with pkgs;
    [
      fd
      hyperfine
      jq
      php
      readline
      ripgrep
      wget
      xz
    ]
    ++ lib.optionals pkgs.stdenv.isLinux [
      gcc # C/C++ compiler (provides gcc, g++, cc)
    ];
}
