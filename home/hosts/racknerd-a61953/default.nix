{ config, pkgs, ... }:

{
  imports = [
    ../../modules/default.nix
  ];

  dconf.enable = false;
}
