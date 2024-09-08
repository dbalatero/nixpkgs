{ config, lib, pkgs, ... }:

{
  imports = [
    ./modules/common.nix
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";

  # Use the default C-b on this Linux server, to avoid colliding when sshing to
  # this machine.
  programs.tmux.prefix = null;
}
