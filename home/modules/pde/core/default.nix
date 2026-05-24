{
  lib,
  pkgs,
  ...
}: {
  home.packages = with pkgs;
    [
      fd
      jq
      readline
      ripgrep
      wget
      xz
    ]
    ++ lib.optionals pkgs.stdenv.isLinux [
      gcc # C/C++ compiler (provides gcc, g++, cc)
    ];
}
