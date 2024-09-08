{ config, lib, pkgs, ... }:

{
  imports = [
    ./home-manager.nix

    ./audio
    ./fonts
    ./git
    ./ruby
    ./tmux
    ./vscode
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
