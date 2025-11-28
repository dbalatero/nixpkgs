{ config, pkgs, ... }:

{
  imports = [
    ../../modules/default.nix
  ];

  home.homeDirectory = "/Users/dbalatero";
  home.username = "dbalatero";
}