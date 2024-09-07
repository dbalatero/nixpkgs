{ config, lib, pkgs, ... }:

{
  imports = [
    ./home-manager.nix

    ./git
    ./tmux
  ];

  home.packages = with pkgs; [
    coreutils
    curl
    fd
    gh
    gnutar
    pgcli
    redis
    ripgrep
    sl
    wget
  ];
}
