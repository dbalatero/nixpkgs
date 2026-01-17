{
  config,
  lib,
  pkgs,
  ...
}: {
  # Base system packages for all NixOS machines
  environment.systemPackages = with pkgs; [
    git
    neovim
    vim
    wget

    # Network utilities
    net-tools  # ifconfig, netstat, route, etc.
  ];
}
