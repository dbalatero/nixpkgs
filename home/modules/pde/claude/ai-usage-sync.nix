{config, lib, pkgs, ...}: {
  home.activation.copyClaudeConfigToAiUsage = lib.hm.dag.entryAfter ["writeBoundary"] ''
    AI_USAGE_DIR="$HOME/code/ai-usage"
    GIT="${pkgs.git}/bin/git"
    export GIT_SSH_COMMAND="${pkgs.openssh}/bin/ssh"

    if [ -d "$AI_USAGE_DIR" ]; then
      cd "$AI_USAGE_DIR"

      # Check we're on main branch
      CURRENT_BRANCH=$($GIT branch --show-current)
      if [ "$CURRENT_BRANCH" != "main" ]; then
        echo "ERROR: ai-usage repo is on branch '$CURRENT_BRANCH', not 'main'."
        echo "Please switch to main branch in $AI_USAGE_DIR before running switch."
        exit 1
      fi

      # Check for unstaged/uncommitted changes before we start
      if ! $GIT diff --quiet || ! $GIT diff --cached --quiet; then
        echo "ERROR: ai-usage repo has unstaged or uncommitted changes."
        echo "Please commit or stash your changes in $AI_USAGE_DIR before running switch."
        exit 1
      fi

      echo "Found ai-usage repo, copying Claude config files..."
      mkdir -p "$AI_USAGE_DIR/db"

      cp "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/claude/config/global-instructions.md" \
         "$AI_USAGE_DIR/db/CLAUDE.md"
      cp "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/claude/config/keybindings.json" \
         "$AI_USAGE_DIR/db/keybindings.json"

      echo "Claude config files copied to $AI_USAGE_DIR/db/"

      # Check if there are changes to commit (including untracked files in db/)
      $GIT add -A db/
      if ! $GIT diff --cached --quiet; then
        echo "Changes detected, committing to ai-usage..."
        $GIT commit -m "db: updating my configuration"

        # Try to pull --rebase and push, but recover gracefully if offline
        PULL_OUTPUT=$($GIT pull --rebase origin main 2>&1) && PULL_SUCCESS=1 || PULL_SUCCESS=0
        if [ "$PULL_SUCCESS" = "1" ]; then
          PUSH_OUTPUT=$($GIT push -u origin main 2>&1) && PUSH_SUCCESS=1 || PUSH_SUCCESS=0
          if [ "$PUSH_SUCCESS" = "1" ]; then
            echo "Successfully pushed changes to ai-usage."
          else
            echo "WARNING: 'git push' failed: $PUSH_OUTPUT"
            echo "Committed anyways. Next time you have connectivity and run switch this should recover."
          fi
        else
          echo "WARNING: 'git pull --rebase' failed: $PULL_OUTPUT"
          echo "Committed anyways. Next time you have connectivity and run switch this should recover."
        fi
      else
        echo "No changes to Claude config files."
      fi
    fi
  '';
}
