{
  description = "Home Manager flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/master";
    home-manager = {
      url = "github:nix-community/home-manager/release-24.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixvim = {
      url = "github:nix-community/nixvim";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    darwin = {
      url = "github:LnL7/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs: {
    darwinConfigurations = {
      nix-machine2 = inputs.darwin.lib.darwinSystem {
        system = "aarch64-darwin";
        modules = [
          ./darwin
          inputs.home-manager.darwinModules.home-manager {
            home-manager = {
              users.dbalatero = {
                # thank god: https://github.com/ddervisis/dotnix/blob/72ea2067d61dddaa1c1ce8c277040f80c59d9bcf/darwin/default.nix#L29
                imports = [
                  (import ./home/nix-machine2.nix)
                  inputs.nixvim.homeManagerModules.nixvim
                ];
              };
              extraSpecialArgs = { inherit inputs; };
            };

            users.users.dbalatero.home = "/Users/dbalatero";
          }
        ];
        specialArgs = { inherit inputs; };
      };
    };

    homeConfigurations = {
      # HLDM RackNerd server
      racknerd-a61953 = inputs.home-manager.lib.homeManagerConfiguration {
        pkgs = inputs.nixpkgs.legacyPackages.x86_64-linux;
        modules = [
          inputs.nixvim.homeManagerModules.nixvim
          ./home/racknerd-a61953.nix
        ];
      };

      # WSL
      tiger = inputs.home-manager.lib.homeManagerConfiguration {
        pkgs = inputs.nixpkgs.legacyPackages.x86_64-linux;
        modules = [
          inputs.nixvim.homeManagerModules.nixvim
          ./home/tiger.nix
        ];
      };
    };
  };
}
