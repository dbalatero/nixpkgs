{
  pkgs,
  lib,
  ...
}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui
    ../../modules/gui/macos
    ../../modules/pde/claude/ai-usage-sync.nix
  ];

  home.homeDirectory = "/Users/db";
  home.username = "db";

  programs.git.settings.user.email = "db@graphite.com";

  programs.ssh = {
    matchBlocks = {
      "*" = {
        identityAgent = "~/Library/Group\\ Containers/2BUA8C4S2C.com.1password/t/agent.sock";
      };
    };
  };

  home.packages = with pkgs; [
    caddy
    cursor-cli

    (writeShellScriptBin "copy-repo" ''
      set -euo pipefail

      SOURCE="$HOME/code/monologue"

      if [ ! -d "$SOURCE" ]; then
        echo "Error: source repo $SOURCE does not exist"
        exit 1
      fi

      read -rp "New repo name: " name

      if [ -z "$name" ]; then
        echo "Error: name cannot be empty"
        exit 1
      fi

      TARGET="$HOME/code/$name"

      if [ -e "$TARGET" ]; then
        echo "Error: $TARGET already exists"
        exit 1
      fi

      echo "Cloning $SOURCE -> $TARGET..."
      ${lib.getExe pkgs.git} clone "$SOURCE" "$TARGET"

      echo "Setting origin to github..."
      ${lib.getExe pkgs.git} -C "$TARGET" remote set-url origin git@github.com:withgraphite/monologue.git

      echo "Symlinking .envrc..."
      ln -sf "$SOURCE/.envrc" "$TARGET/.envrc"

      read -rp "Run ./setup.sh in $TARGET? [y/N] " run_setup
      if [ "$run_setup" = "y" ] || [ "$run_setup" = "Y" ]; then
        cd "$TARGET"
        ./setup.sh
      fi

      echo "Done! Repo is at $TARGET"
    '')
  ];

  programs.starship.settings = {
    format = lib.mkForce (lib.concatStrings [
      "$hostname"
      "$directory"
      "$git_branch"
      "$aws"
      "$line_break"
      "$character"
    ]);

    aws.disabled = lib.mkForce false;
  };

  programs.zsh.initContent = lib.mkAfter ''
    export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"

    [ -f "$HOME/code/monologue/tools/vpn/bin/shell-integration.sh" ] && source "$HOME/code/monologue/tools/vpn/bin/shell-integration.sh"
  '';
}
