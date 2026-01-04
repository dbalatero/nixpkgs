{pkgs, ...}: {
  stylix = {
    enable = true;

    # https://github.com/tinted-theming/schemes/blob/spec-0.11/base16/catppuccin-macchiato.yaml
    base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-macchiato.yaml";

    targets = {
      ghostty.enable = false;

      # Use a overridden tmux scheme for now
      tmux.enable = false;

      # Disable vim target - using native catppuccin.nvim plugin instead
      # (provides full 26+ color palette vs stylix's base16 simplified 16-color version)
      vim.enable = false;

      # Disable ALL Qt/KDE/GTK theming - Kvantum breaks Plasma 6
      # See: https://github.com/nix-community/stylix/issues/835
      kde.enable = false;
      qt.enable = false;
      gtk.enable = false;  # Disable GTK theming to avoid .gtkrc-2.0 conflicts
    };
  };
}
