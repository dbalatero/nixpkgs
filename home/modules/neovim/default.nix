{ config, lib, pkgs, pkgsUnstable, ... }:

{
  home.packages = with pkgs; [
    pkgsUnstable.neovim

    bat
    clang
    libgcc
    luajit
    luajitPackages.luarocks
    tree-sitter
  ];

  xdg.configFile."nvim".source = config.lib.file.mkOutOfStoreSymlink "${config.xdg.configHome}/nixpkgs/home/modules/neovim/config";
}
