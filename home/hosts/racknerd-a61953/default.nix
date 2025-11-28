{
  config,
  pkgs,
  ...
}: {
  imports = [
    ../../modules/default.nix
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";

  dconf.enable = false;
}
