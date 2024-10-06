{pkgs, ...}: {
  imports = [
    ./home-manager.nix
    ./audio
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
        name = "JetBrainsMono";
      };

      sizes = {
        terminal = 16;
      };
    };
  };
}
