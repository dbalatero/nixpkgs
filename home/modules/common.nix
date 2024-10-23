{pkgs, ...}: {
  imports = [
    ./home-manager.nix
    ./audio
    ./alacritty
    ./backups
    ./core
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

  stylix = {
    fonts = {
      monospace = {
        package = pkgs.nerdfonts.override {
          # Only install the listed font(s)
          fonts = ["JetBrainsMono"];
        };
        name = "JetBrainsMonoNL Nerd Font";
      };

      sizes = {
        terminal = 16;
      };
    };
  };
}
