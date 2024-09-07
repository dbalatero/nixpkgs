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

    diff-so-fancy = {
      enable = true;
    };

    extraConfig = {
      github.user = "dbalatero";
      init.defaultBranch = "main";

      advice.statusHints = false;

      apply.whitespace = "nowarn";

      branch.autosetupmerge = true;

      color.ui = true;
      color.branch.current = "yellow reverse";
      color.branch.local = "yellow";
      color.branch.remote = "green";

      color.diff.meta = "yellow bold";
      color.diff.frag = "magenta bold";
      color.diff.old = "red";
      color.diff.new = "green";

      core.autocrlf = false;
      core.commitGraph = true;
      core.editor = "nvim";
      core.fsmonitor = true;
      core.precomposeUnicode = true;

      diff.algorithm = "patience";

      # Git diff will use (i)ndex, (w)ork tree, (c)ommit and (o)bject
      # instead of a/b/c/d as prefixes for patches
      diff.mnemonicprefix = true;

      feature.manyFiles = 1;

      filter.lfs.clean = "git-lfs clean -- %f";
      filter.lfs.process = "git-lfs filter-process";
      filter.lfs.required = true;
      filter.lfs.smudge = "git-lfs smudge -- %f";

      format.pretty = "format:%C(blue)%ad%Creset %C(yellow)%h%C(green)%d%Creset %C(blue)%s %C(magenta) [%an]%Creset";

      gc.writecommitGraph = true;

      help.autocorrect = 0;

      interactive.singlekey = true;

      mergetool.prompt = false;

      merge.conflictstyle = "diff3";
      merge.summary = true;
      merge.tool = "nvimdiff";
      merge.verbosity = 1;
 
      # fast-forwards only
      pull.ff = "only";

      push.autoSetupRemote = true;

      # 'git push' will push the current branch to its tracking branch
      # the usual default is to push all branches
      push.default = "current";

      # Remember my merges:
      #   http://gitfu.wordpress.com/2008/04/20/git-rerere-rereremember-what-you-did-last-time/
      rerere.enabled = true;
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
