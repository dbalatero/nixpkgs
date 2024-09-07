{ config, lib, pkgs, ... }:

{
  home.packages = with pkgs; [
    diff-so-fancy
    git
    lazygit

    (writeShellScriptBin "git-churn" (builtins.readFile ./bin/git-churn.sh))
    (writeShellScriptBin "git-delete-merged-branches" (builtins.readFile ./bin/git-delete-merged-branches.sh))
    (writeShellScriptBin "git-local-repos" (builtins.readFile ./bin/git-local-repos.sh))
    (writeShellScriptBin "git-main-branch" (builtins.readFile ./bin/git-main-branch.sh))
    (writeShellScriptBin "git-switch-interactive" (builtins.readFile ./bin/git-switch-interactive.sh))
    (writeShellScriptBin "git-what-i-did" (builtins.readFile ./bin/git-what-i-did.sh))
  ];

  xdg.configFile."git/message".text = ''


# 50-character subject line
#
# 72-character wrapped longer description. This should answer:
#
# * Why was this change necessary?
# * How does it address the problem?
# * Are there any side effects?
#
# Include a link to the ticket, if any.
  '';

  programs.git = {
    enable = true;
    userName = "David Balatero";
    userEmail = "dbalatero@users.noreply.github.com";

    extraConfig = {
      github.user = "dbalatero";
      init.defaultBranch = "main";
    };

    attributes = [
      "*.rb diff=ruby"
      "*.rake diff=ruby"
    ];

    ignores = [
      ###  OSX 
      ".DS_Store"

      # Thumbnails
      "._*"

      # Files that might appear on external disk
      ".Spotlight-V100"
      ".Trashes"

      ### Windows
      # Windows image file caches
      "Thumbs.db"

      # Folder config file
      "Desktop.ini"

      # Tags
      # Ignore tags created by etags and ctags
      "/TAGS"
      "/tags"

      ### Vim
      ".*.sw[a-z]"
      "*.un~"
      "Session.vim"

      ### SASS
      ".sass-cache"

      ### Gtags
      "/GPATH"
      "/GRTAGS"
      "/GTAGS"

      ".dir-locals.el"

      ".#*"

      "/tags.lock"
      "/tags.temp"
      "/tags"
      ".gutentag"
      "/tags.files"

      ".tern-project"
      ".projectroot"

      "/TODO"
    ];
  };
}
