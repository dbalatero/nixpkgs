{ config, lib, pkgs, ... }:

{
  imports = [
    ./modules/common.nix
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";
}
