{
  ...
}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui/nixos
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";
}
