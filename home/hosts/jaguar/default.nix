{pkgs, ...}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui
    ../../modules/gui/macos
  ];

  home.homeDirectory = "/Users/db";
  home.username = "db";

  programs.git.settings.user.email = "db@graphite.dev";

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
}
