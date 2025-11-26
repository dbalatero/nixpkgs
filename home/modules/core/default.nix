{ config, pkgs, ... }:

{
  programs.home-manager.enable = true;

  home.username = "dbalatero";
  home.stateVersion = "25.05";
  home.homeDirectory = "/home/dbalatero";

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # Silence home-manager news
  news.display = "silent";
}
