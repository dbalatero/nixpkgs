{pkgs, ...}: {
  stylix = {
    enable = true;

    # https://github.com/tinted-theming/schemes/blob/spec-0.11/base16/catppuccin-mocha.yaml
    base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";

    targets = {
      # Use a overridden tmux scheme for now
      tmux.enable = false;

      # Disable vim target - using native catppuccin.nvim plugin instead
      # (provides full 26+ color palette vs stylix's base16 simplified 16-color version)
      vim.enable = false;
    };
  };
}
