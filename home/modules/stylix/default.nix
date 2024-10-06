{pkgs, ...}: {
  stylix = {
    enable = true;

    # Shut up, stylix
    image = ../kitty/images/gradient_background.png;

    # https://github.com/tinted-theming/schemes/blob/spec-0.11/base16/catppuccin-mocha.yaml
    base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";

    # For now keep the tmux theme we have
    targets.tmux.enable = false;
  };
}
