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
}
