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
}
