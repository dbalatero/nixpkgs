{pkgs, ...}: {
  imports = [
    ./home-manager.nix

    ./audio
    ./fonts
    ./git
    ./neovim
    ./node
    ./python
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
