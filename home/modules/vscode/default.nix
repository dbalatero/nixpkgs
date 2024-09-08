{ config, lib, pkgs, ... }:

{
  home.file."Library/Application Support/Code/User" = {
    recursive = true;
    source = ./config;
  };
}
