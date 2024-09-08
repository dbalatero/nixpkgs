{ config, lib, pkgs, ... }:

{
  home.packages = with pkgs; [
    # Prevent collision with clang
    #  https://github.com/nix-community/home-manager/issues/1668
    (hiPrio gcc14)
    gnumake
    openssl_3_3
    pkg-config
    ruby_3_3
    zlib
  ];

  programs.rbenv = {
    enable = true;

    plugins = [
      {
        name = "ruby-build";
        src = pkgs.fetchFromGitHub {
          owner = "rbenv";
          repo = "ruby-build";
          rev = "v20240903";
          hash = "sha256-lhsdcTPVJkLURSz4yd952eGvReeVU10I9NxosMvKYSk=";
        };
      }
      {
        name = "rbenv-default-gems";
        src = pkgs.fetchFromGitHub {
          owner = "rbenv";
          repo = "rbenv-default-gems";
          rev = "de4ff2e101c9221dcd92ed91a41edcea2be41945";
          hash = "sha256-SCY7C4pxfAWrMdp+Rp0g6nnt424SR0XZPtF8h8A4Mu4=";
        };
      }
    ];
  };

  home.file.".pryrc".source = ./pryrc.rb;
}
