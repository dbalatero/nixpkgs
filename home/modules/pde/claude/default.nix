{
  config,
  pkgs,
  ...
}: let
  configDir = "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/claude/config";
in {
  home.packages = with pkgs; [
    claude-code
  ];

  # Writable symlinks to claude config - allows direct editing without Nix rebuilds
  # Note: global-instructions.md is renamed to avoid Claude interpreting it in this repo
  home.file.".claude/CLAUDE.md".source = config.lib.file.mkOutOfStoreSymlink
    "${configDir}/global-instructions.md";

  home.file.".claude/keybindings.json".source = config.lib.file.mkOutOfStoreSymlink
    "${configDir}/keybindings.json";

  # Commands - custom slash commands for Claude Code
  home.file.".claude/commands".source = config.lib.file.mkOutOfStoreSymlink
    "${configDir}/commands";

  # Agents - custom agents for specialized tasks
  home.file.".claude/agents".source = config.lib.file.mkOutOfStoreSymlink
    "${configDir}/agents";

  # Settings - Claude Code settings
  home.file.".claude/settings.json".source = config.lib.file.mkOutOfStoreSymlink
    "${configDir}/settings.json";
}
