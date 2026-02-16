{
  config,
  lib,
  pkgs,
  ...
}: {
  home.packages = with pkgs; [
    gh
    git
    go-jira
    (writeShellScriptBin "git-churn" (builtins.readFile ./bin/git-churn.sh))
    (writeShellScriptBin "git-delete-merged-branches" (builtins.readFile ./bin/git-delete-merged-branches.sh))
    (writeShellScriptBin "git-local-repos" (builtins.readFile ./bin/git-local-repos.sh))
    (writeShellScriptBin "git-main-branch" (builtins.readFile ./bin/git-main-branch.sh))
    (writeShellScriptBin "git-submit" (builtins.readFile ./bin/git-submit.sh))
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

  programs.lazygit = {
    enable = true;
    enableZshIntegration = true;
  };

  programs.delta = {
    enable = true;
    enableGitIntegration = true;
  };

  programs.git = {
    enable = true;

    settings = {
      user = {
        name = lib.mkDefault "David Balatero";
        email = lib.mkDefault "dbalatero@users.noreply.github.com";
      };

      alias = {
        # add
        a = "add";

        # branch
        b = "branch -v"; # branch (verbose)
        recent-branches = "!git for-each-ref --count=5 --sort=-committerdate refs/heads/ --format='%(refname:short)'";

        # commit
        amend = "commit --amend"; # amend your last commit
        c = "commit -m"; # commit with message
        ca = "commit -am"; # commit all with message
        ci = "commit"; # commit

        # checkout
        co = "checkout"; # checkout
        nb = "checkout -b"; # create and switch to a new branch (mnemonic: "git new branch branchname...")
        m = "checkout master"; # checkout main branch

        done = "!git fetch origin $(git main-branch):$(git main-branch) && git checkout $(git main-branch)";

        # cherry-pick
        cp = "cherry-pick -x"; # grab a change from a branch

        # diff
        d = "diff"; # diff unstaged changes
        dc = "diff --cached"; # diff staged changes
        last = "diff HEAD^"; # diff last committed change

        # log
        l = "log --graph --date=short";
        changes = "log --pretty=format:\"%h %cr %cn %Cgreen%s%Creset\" --name-status";
        short = "log --pretty=format:\"%h %cr %cn %Cgreen%s%Creset\"";
        simple = "log --pretty=format:\" * %s\"";
        shortnocolor = "log --pretty=format:\"%h %cr %cn %s\"";

        # pull
        pl = "pull"; # pull

        # push
        ps = "push -u"; # push
        p = "push -u --force-with-lease";
        please = "push -u --force-with-lease";

        # rebase
        rc = "rebase --continue"; # continue rebase
        rs = "rebase --skip"; # skip rebase

        # remote
        r = "remote -v"; # show remotes (verbose)

        ### sync
        # Quick sync (non-interactive mode)
        qsync = "!git fetch origin $(git main-branch):$(git main-branch) && git rebase --no-keep-empty $(git main-branch)";

        # interactive sync your current branch with master
        sync = "!git fetch origin $(git main-branch):$(git main-branch) && git rebase --no-keep-empty -i $(git main-branch)";

        take-master = "!git checkout --ours $1 && git add $1 && git status";

        # respond to PR feedback
        respond = "!git commit --amend --no-edit && git push --force-with-lease";

        # fix your branch when it's missing upstream
        upstream = "!git branch --set-upstream-to=origin/$(git rev-parse --abbrev-ref HEAD) $(git rev-parse --abbrev-ref HEAD)";

        # reset
        unstage = "reset HEAD"; # remove files from index (tracking)

        # switch branches interactive
        si = "switch-interactive";

        # stash
        ss = "stash"; # stash changes
        sl = "stash list"; # list stashes
        sa = "stash apply"; # apply stash (restore changes)
        sd = "stash drop"; # drop stashes (destory changes)

        # status
        s = "status"; # status
        st = "status"; # status
        stat = "status"; # status

        # tag
        t = "tag -n"; # show tags with <n> lines of each tag message
      };

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

      commit.template = "${config.xdg.configHome}/git/message";

      core.autocrlf = false;
      core.commitGraph = true;
      core.deltabasecachelimit = "4g";
      core.editor = "nvim";
      core.precomposeUnicode = true;
      core.preloadindex = true;
      core.fsmonitor = true;
      core.untrackedCache = true;

      diff.algorithm = "patience";

      # Git diff will use (i)ndex, (w)ork tree, (c)ommit and (o)bject
      # instead of a/b/c/d as prefixes for patches
      diff.mnemonicprefix = true;

      # http://stackoverflow.com/questions/18257622/why-is-git-core-preloadindex-default-value-false
      feature.manyFiles = true;

      fetch.prune = true;

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

      work.features.gh = true;
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
