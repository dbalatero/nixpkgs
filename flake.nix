{
  description = "Home Manager flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/master";
    darwin = {
      url = "github:lnl7/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    home-manager = {
      url = "github:nix-community/home-manager/release-24.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixvim = {
      url = "github:nix-community/nixvim";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    home-manager,
    nixpkgs,
    nix-darwin,
    nixvim,
    ...
  } @ inputs: let
    # Stole from: https://github.com/mhanberg/.dotfiles/blob/main/flake.nix
    mkDarwin = {extraDarwinModules ? []}:
      nix-darwin.lib.darwinSystem {
        system = "aarch64-darwin";
        modules = [./home/modules/darwin] ++ extraDarwinModules;
        specialArgs = {inherit self;};
      };

    mkHm = {
      extraModules ? [],
      arch,
    }:
      home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.${arch};
        modules =
          [
            nixvim.homeManagerModules.nixvim
          ]
          ++ (
            if arch == "aarch64-darwin"
            then ["./home/modules/darwin/home-manager.nix"]
            else []
          )
          ++ extraModules;
      };
  in {
    darwinConfigurations = {
      nix-machine = mkDarwin {};
    };

    homeConfigurations = {
      # HLDM RackNerd server
      racknerd-a61953 = mkHm {
        arch = "x86_64-linux";
        extraModules = [./home/racknerd-a61953.nix];
      };

      # WSL
      tiger = mkHm {
        arch = "x86_64-linux";
        extraModules = [./home/tiger.nix];
      };

      # macOS testbed
      nix-machine = mkHm {
        arch = "aarch64-darwin";
        extraModules = [./home/nix-machine.nix];
      };
    };
  };
}
