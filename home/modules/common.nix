{ config, lib, pkgs, ... }:

{
  imports = [
    ./home-manager.nix

    ./git
    ./tmux
  ];
}
