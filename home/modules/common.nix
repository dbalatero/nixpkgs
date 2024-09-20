{pkgs, ...}: {
  imports = [
    ./home-manager.nix

    ./audio
    ./backups
    ./fonts
    ./git
    ./neovim
    ./node
    ./python
    ./ruby
    ./tmux
    ./vscode
    ./wezterm
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
