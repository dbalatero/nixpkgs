{pkgs, ...}: {
  home.packages = with pkgs; [
    # Password manager
    _1password-gui

    # Web browser
    (google-chrome.override {
      commandLineArgs = [
        # Better font rendering
        "--force-device-scale-factor=1"
        "--enable-features=WebUIDarkMode"
        "--disable-features=UseChromeOSDirectVideoDecoder"

        # Font rendering improvements
        "--enable-font-antialiasing"
        "--disable-lcd-text"
      ];
    })

    # Communication
    discord
    slack
  ];
}
