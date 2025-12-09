{pkgs, ...}: {
  programs.ghostty = {
    enable = true;

    # On macOS, we install via homebrew cask, so don't install via nix
    # On Linux, install from nixpkgs
    package =
      if pkgs.stdenv.isDarwin
      then null
      else pkgs.ghostty;

    settings = {
      # General settings
      term = "xterm-256color";
      font-family = "BerkeleyMono Nerd Font Mono";
      font-style = "Normal";
      font-size = 18;
      cursor-style = "block";
      window-theme = "dark";
      background-opacity = 1.0;
      macos-option-as-alt = true;
      macos-non-native-fullscreen = true;
      fullscreen = true;
      window-decoration = false;
      window-padding-x = 0;
      window-padding-y = 0;
      window-save-state = "default";
      shell-integration = "zsh";
      mouse-hide-while-typing = true;
      window-colorspace = "display-p3";

      # Match spacing "feel" from Alacritty/iTerm
      adjust-cell-width = "-5%";
      adjust-cell-height = "5%";
      font-thicken = true;

      # 50mb scrollback limit, in bytes
      scrollback-limit = 50000000;
      bell-features = "no-audio,no-system,no-attention,no-title,no-border";

      theme = "Catppuccin Macchiato";

      # Optional local config file
      config-file = "?config.local";
    };
  };
}
