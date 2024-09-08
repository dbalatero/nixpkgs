{ config, lib, pkgs, ... }:

{
  imports = [
    ./home-manager.nix

    ./git
    ./ruby
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
