{
  imports = [
    ./modules/common.nix
    ./modules/darwin/home-manager.nix
  ];

  home.homeDirectory = "/Users/dbalatero";
  home.username = "dbalatero";
}
