{pkgs, ...}: {
  stylix = {
    enable = true;

    # https://github.com/tinted-theming/schemes/blob/spec-0.11/base16/catppuccin-mocha.yaml
    base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";

    fonts = {
      monospace = {
        package = pkgs.nerdfonts;
        name = "JetBrainsMono";
      };

      sizes = {
        terminal = 16;
      };
    };

    # For now keep the tmux theme we have
    targets.tmux.enable = false;
  };
}
