{
  description = "Home Manager flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/release-24.05";
    nixpkgsUnstable.url = "github:NixOS/nixpkgs/master";
    home-manager = {
      url = "github:nix-community/home-manager/release-24.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs: {
    homeConfigurations = {
      # HLDM RackNerd server
      racknerd-a61953 = inputs.home-manager.lib.homeManagerConfiguration {
        pkgs = inputs.nixpkgs.legacyPackages.x86_64-linux;
        modules = [
          ./home/racknerd-a61953.nix
        ];
        extraSpecialArgs = {
          pkgsUnstable = inputs.nixpkgsUnstable.legacyPackages.x86_64-linux;
        };
      };
    };
  };
}
