{ config, lib, pkgs, ... }:

{
  programs.rbenv.enable = true;

  home.file.".pryrc".source = ./pryrc.rb;
}
