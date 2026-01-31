{pkgs, lib, ...}: {
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
  ];

  programs.zsh.initContent = lib.mkAfter ''
    export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
  '';
}
