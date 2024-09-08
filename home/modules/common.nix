{ config, lib, pkgs, ... }:

{
  imports = [
    ./home-manager.nix

    ./git
    ./tmux
    ./zsh
  ];

  home.packages = with pkgs; [
    coreutils
    curl
    fd
    gh
    gnutar
    pgcli
    readline
    redis
    ripgrep
    sl
    wget
    xz
  ];
}
