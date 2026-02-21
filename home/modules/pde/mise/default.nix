{lib, pkgs, ...}: {
  home.file.".default-gems".text = ''
    bundler
  '';
  programs.zsh.sessionVariables = {
    MISE_NODE_COREPACK = "true";
  };
  programs.mise = {
    enable = true;
    enableZshIntegration = true;
    globalConfig = {
      tools = {
        node = "lts";
        python = "latest";
      } // lib.optionalAttrs pkgs.stdenv.isDarwin {
        ruby = "latest";
      };
      settings = {
        idiomatic_version_file_enable_tools = ["node" "python" "ruby"];
        not_found_auto_install = true;
      } // lib.optionalAttrs pkgs.stdenv.isLinux {
        all_compile = false;
      };
    };
  };

  # On Linux, use Nix-packaged Ruby instead of mise (ruby-build compilation
  # is broken on NixOS and prebuilt binaries aren't supported yet in mise)
  home.packages = lib.optionals pkgs.stdenv.isLinux [
    pkgs.ruby
  ];
}
