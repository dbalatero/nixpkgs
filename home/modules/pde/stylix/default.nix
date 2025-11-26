{pkgs, ...}: {
  stylix = {
    enable = true;

    # https://github.com/tinted-theming/schemes/blob/spec-0.11/base16/catppuccin-mocha.yaml
    base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";

    # Use a overridden tmux scheme for now
    targets.tmux.enable = false;
  };
}
