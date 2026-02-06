{
  description = "Monorepo for dbalatero system configurations";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
    nix-homebrew.url = "github:zhaofengli/nix-homebrew";
    claude-code.url = "github:sadjow/claude-code-nix";

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

    plasma-manager = {
      url = "github:nix-community/plasma-manager";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.home-manager.follows = "home-manager";
    };

    nix-flatpak = {
      url = "github:gmodena/nix-flatpak";
    };
  };

  outputs = inputs @ {
    self,
    nixpkgs,
    darwin,
    home-manager,
    nixvim,
    stylix,
    plasma-manager,
    nix-homebrew,
    nix-flatpak,
    claude-code,
  }: {
    homeConfigurations."racknerd-a61953" = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      modules = [
        {nixpkgs.overlays = [claude-code.overlays.default];}
        nixvim.homeModules.nixvim
        stylix.homeModules.stylix
        ./home/hosts/racknerd-a61953
      ];
    };

    # NixOS machines
    # NEW_HOST_SENTINEL - Do not remove this comment (used by bin/new-host)
    nixosConfigurations.panther = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./hosts/panther/configuration.nix
        ./hosts/panther/hardware-configuration.nix
        home-manager.nixosModules.home-manager
        {
          nixpkgs.config.allowUnfree = true;
          nixpkgs.overlays = [claude-code.overlays.default];

          home-manager = {
            users.dbalatero = {
              imports = [
                ./home/hosts/panther
                nixvim.homeModules.nixvim
                stylix.homeModules.stylix
                plasma-manager.homeModules.plasma-manager
                nix-flatpak.homeManagerModules.nix-flatpak
              ];
            };

            useGlobalPkgs = true;
            extraSpecialArgs = {inherit inputs;};
          };
        }
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
          nixpkgs.overlays = [claude-code.overlays.default];

          home-manager = {
            users.dbalatero = {
              imports = [
                (import ./home/hosts/lion)
                nixvim.homeModules.nixvim
                stylix.homeModules.stylix
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

    # work laptop
    darwinConfigurations."jaguar" = darwin.lib.darwinSystem {
      system = "aarch64-darwin";
      modules = [
        nix-homebrew.darwinModules.nix-homebrew
        {
          nix-homebrew = {
            # Install Homebrew under the default prefix
            enable = true;

            # User owning the Homebrew prefix
            user = "db";
          };
        }
        ./darwin/hosts/jaguar
        {
          networking.localHostName = "jaguar";
        }
        home-manager.darwinModules.home-manager
        {
          # Allow unfree packages at the system level
          nixpkgs.config.allowUnfree = true;
          nixpkgs.overlays = [claude-code.overlays.default];

          home-manager = {
            users.db = {
              imports = [
                (import ./home/hosts/jaguar)
                nixvim.homeModules.nixvim
                stylix.homeModules.stylix
              ];
            };
            useGlobalPkgs = true;
            extraSpecialArgs = {inherit inputs;};
          };

          users.users.db.home = "/Users/db";
        }
      ];

      specialArgs = {inherit inputs;};
    };
  };
}
