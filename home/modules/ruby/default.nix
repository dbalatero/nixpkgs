{ config, lib, pkgs, ... }:

{
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
    ];
  };

  home.file.".pryrc".source = ./pryrc.rb;
}
