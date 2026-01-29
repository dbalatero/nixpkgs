{pkgs, ...}: {
  home.packages = with pkgs; [
    claude-code
  ];

  home.file.".claude/CLAUDE.md".text = ''
    # Personal Claude Code Instructions

    ## Search Tools

    Never use `grep` or `find` for searching. Always use:
    - `fd` for finding files
    - `rg` (ripgrep) for searching file contents
  '';

  home.file.".claude/keybindings.json".text = builtins.toJSON {
    "$schema" = "https://platform.claude.com/docs/schemas/claude-code/keybindings.json";
    "$docs" = "https://code.claude.com/docs/en/keybindings";
    bindings = [
      {
        context = "Global";
        bindings = {
          "alt+t" = "app:toggleTranscript";
          "ctrl+o" = null; # unbind default
        };
      }
    ];
  };
}
