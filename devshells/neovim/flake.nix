{
  description = "Neovim contributor dev shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [
        cmake
        ninja
        gcc
        gnumake
        ccache
        gettext
        curl
        pkg-config
        unzip
        gdb
        valgrind
        lua-language-server
      ];

      shellHook = ''
        export CCACHE_DIR="$HOME/.cache/ccache"
      '';
    };
  };
}
