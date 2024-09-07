{ config, lib, pkgs, ... }:

{
  home.packages = with pkgs; [
    diff-so-fancy
    git
    lazygit
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
