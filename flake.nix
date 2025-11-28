{
  description = "Monorepo for dbalatero system configurations";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

    darwin = {
      url = "github:lnl7/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nixvim = {
      url = "github:nix-community/nixvim";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    stylix = {
      url = "github:danth/stylix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    darwin,
    home-manager,
    nixvim,
    stylix,
  }: {
    homeConfigurations."racknerd-a61953" = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      modules = [
        nixvim.homeModules.nixvim
        stylix.homeModules.stylix
        ./home/hosts/racknerd-a61953
      ];
    };

    # Macbook Air
    darwinConfigurations."lion" = darwin.lib.darwinSystem {
      system = "aarch64-darwin";
      modules = [
        ./darwin/hosts/lion
        home-manager.darwinModules.home-manager
        {
          home-manager = {
            users.dbalatero = {
              imports = [
                ./home/hosts/lion
                nixvim.homeManagerModules.nixvim
                stylix.homeManagerModules.stylix
              ];
            };
            useGlobalPkgs = true;
            extraSpecialArgs = { inherit nixpkgs; };
          };
          users.users.dbalatero.home = "/Users/dbalatero";
        }
      ];
      specialArgs = { inherit nixpkgs; };
    };
  };
}
