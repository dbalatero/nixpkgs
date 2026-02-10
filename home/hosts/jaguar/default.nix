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

    (writeShellScriptBin "copy-repo" (builtins.readFile ./bin/copy-repo.sh))
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
