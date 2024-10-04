{...}: {
  imports = [
    ./modules/common.nix
    ./modules/darwin
    ./modules/stripe
  ];

  home.homeDirectory = "/Users/dbalatero";
  home.username = "dbalatero";
}
