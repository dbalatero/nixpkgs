{pkgs, ...}: {
  home.packages = with pkgs; [
    # Password manager
    _1password-gui

    # Web browser
    google-chrome
  ];
}
