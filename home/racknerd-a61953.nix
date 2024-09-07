{ config, lib, pkgs, ... }:

{
  imports = [
    ./modules/home-manager.nix
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";
}
