{
  description = "Monorepo for dbalatero system configurations";

  inputs = {
    nix-homebrew.url = "github:zhaofengli/nix-homebrew";

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

  outputs = inputs @ {
    self,
    nixpkgs,
    darwin,
    home-manager,
    nixvim,
    stylix,
    nix-homebrew,
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
        nix-homebrew.darwinModules.nix-homebrew
        {
          nix-homebrew = {
            # Install Homebrew under the default prefix
            enable = true;
            
            # User owning the Homebrew prefix
            user = "dbalatero";
          };
        }
        ./darwin/hosts/lion
        {
          networking.localHostName = "lion";
        }
        home-manager.darwinModules.home-manager
        {
          # Allow unfree packages at the system level
          nixpkgs.config.allowUnfree = true;

          home-manager = {
            users.dbalatero = {
              imports = [
                (import ./home/hosts/lion)
                nixvim.homeManagerModules.nixvim
                stylix.homeManagerModules.stylix
              ];
            };
            useGlobalPkgs = true;
            extraSpecialArgs = {inherit inputs;};
          };

          users.users.dbalatero.home = "/Users/dbalatero";
        }
      ];

      specialArgs = {inherit inputs;};
    };
  };
}
