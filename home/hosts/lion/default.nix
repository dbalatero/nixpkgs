{
  config,
  pkgs,
  ...
}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui
  ];

  home.homeDirectory = "/Users/dbalatero";
  home.username = "dbalatero";
}
