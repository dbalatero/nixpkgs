{ config, lib, pkgs, ... }:

{
  home.packages = with pkgs; [
    bat
    clang
    libgcc
    luajit
    luajitPackages.luarocks
    tree-sitter
  ];

  programs.nixvim = {
    enable = true;
    vimAlias = true;

    colorschemes.catppuccin = {
      enable = true;
      settings = {
        flavour = "mocha";
      };
    };
  };
}
