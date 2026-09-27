{pkgs, ...}: {
  imports = [
    ../../apps/vlc
  ];

  home.packages = with pkgs; [
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

    # E-books
    calibre

    # Communication
    discord
    slack
    zoom-us
  ];
}
