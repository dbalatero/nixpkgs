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

    # Disk utilities
    parted

    # Network utilities
    net-tools  # ifconfig, netstat, route, etc.
  ];
}
