{...}: {
  programs.home-manager.enable = true;

  home.stateVersion = "25.05";

  # Silence home-manager news
  news.display = "silent";

  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
  };
}
