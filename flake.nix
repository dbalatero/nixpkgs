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

  outputs = inputs: let
    mkHm = {
      extraModules ? [],
      arch,
    }:
      inputs.home-manager.lib.homeManagerConfiguration {
        pkgs = inputs.nixpkgs.legacyPackages.${arch};
        modules =
          [
            inputs.nixvim.homeManagerModules.nixvim
          ]
          ++ extraModules;
      };
  in {
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
