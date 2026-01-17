{
  config,
  lib,
  pkgs,
  ...
}: {
  # Enable zsh system-wide (required when setting user shell to zsh)
  programs.zsh.enable = true;

  # User account configuration
  users.users.dbalatero = {
    isNormalUser = true;
    description = "David Balatero";
    initialPassword = "changeme";
    shell = pkgs.zsh;
    extraGroups = [
      "networkmanager"
      "wheel"
      "video"
      "audio"
      "render"  # For modern GPU/DRM access
    ];
  };

  # Allow wheel group to use sudo without password
  security.sudo.wheelNeedsPassword = false;
}
