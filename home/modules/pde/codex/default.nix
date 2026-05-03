{
  config,
  pkgs,
  ...
}: let
  configDir = "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/codex/config";
in {
  home.packages = with pkgs; [
    codex
  ];

  home.file.".codex/config.toml".source = config.lib.file.mkOutOfStoreSymlink
    "${configDir}/config.toml";
}
