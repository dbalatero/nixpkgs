{
  config,
  pkgs,
  ...
}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui
    ../../modules/gui/macos
  ];

  home.homeDirectory = "/Users/dbalatero";
  home.username = "dbalatero";

  programs.ssh = {
    matchBlocks = {
      "*" = {
      identityAgent = "~/Library/Group\\ Containers/2BUA8C4S2C.com.1password/t/agent.sock";
      };
    };
  };
}
