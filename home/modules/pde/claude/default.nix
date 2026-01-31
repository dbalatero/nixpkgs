{
  config,
  pkgs,
  ...
}: {
  home.packages = with pkgs; [
    claude-code
  ];

  # Writable symlinks to claude config - allows direct editing without Nix rebuilds
  # Note: global-instructions.md is renamed to avoid Claude interpreting it in this repo
  home.file.".claude/CLAUDE.md".source = config.lib.file.mkOutOfStoreSymlink
    "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/claude/config/global-instructions.md";

  home.file.".claude/keybindings.json".source = config.lib.file.mkOutOfStoreSymlink
    "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/claude/config/keybindings.json";
}
