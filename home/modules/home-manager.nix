{
  home.stateVersion = "24.05";

  # TODO: bump to 24.11 when they cut one
  home.enableNixpkgsReleaseCheck = false;

  # Let Home Manager install and manage itself.
  programs.home-manager.enable = true;
}
