{
  description = "Monorepo for dbalatero system configurations";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager }: {
    homeConfigurations."racknerd-a61953" = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      modules = [
        {
          home.username = "dbalatero";
          home.homeDirectory = "/home/dbalatero";
          home.stateVersion = "25.05";
          programs.home-manager.enable = true;
        }
      ];
    };
  };
}
