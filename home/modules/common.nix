{pkgs, ...}: {
  imports = [
    ./home-manager.nix

    ./audio
    ./backups
    ./fonts
    ./git
    ./kitty
    ./neovim
    ./node
    ./python
    ./ruby
    ./stylix
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
