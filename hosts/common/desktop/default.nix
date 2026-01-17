{
  config,
  lib,
  pkgs,
  ...
}: {
  # KDE Plasma desktop environment
  services.displayManager.sddm.enable = true;
  services.displayManager.sddm.wayland.enable = true;
  services.desktopManager.plasma6.enable = true;

  # XDG Desktop Portal configuration for KDE Plasma
  xdg.portal = {
    enable = true;
    extraPortals = with pkgs; [
      xdg-desktop-portal-gtk
    ];
  };

  # Enable X11 windowing system (required even for Wayland desktop environments)
  services.xserver.enable = true;

  # Steam
  programs.steam = {
    enable = true;
    remotePlay.openFirewall = true;
    dedicatedServer.openFirewall = true;

    # Add GE-Proton for better game compatibility (includes Battle.net fixes)
    extraCompatPackages = with pkgs; [
      proton-ge-bin
    ];
  };

  # Font configuration
  fonts = {
    fontconfig.enable = true;
    packages = with pkgs; [
      noto-fonts
      noto-fonts-cjk-sans
      noto-fonts-color-emoji
      liberation_ttf
      dejavu_fonts
      ubuntu-classic
      corefonts  # Includes Verdana, Arial, Times New Roman (used by many websites)
    ];
  };

  # GameMode for better gaming performance
  programs.gamemode.enable = true;

  # CPU governor for maximum performance
  powerManagement.cpuFreqGovernor = "performance";

  # Kernel-level keyboard remapping with keyd (works for all apps including games)
  services.keyd = {
    enable = true;
    keyboards = {
      default = {
        ids = ["*"];
        settings = {
          main = {
            # Remap capslock to control
            capslock = "leftcontrol";
          };
        };
      };
    };
  };

  # Keyboard configuration
  services.xserver.xkb.options = "ctrl:nocaps";

  # Keyboard repeat rate (delay in ms, rate in repeats/sec)
  services.xserver.autoRepeatDelay = 200;
  services.xserver.autoRepeatInterval = 30;

  # Audio
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
  };

  # Gaming mouse configuration (ratbagd for Logitech G502)
  services.ratbagd.enable = true;

  # Desktop packages
  environment.systemPackages = with pkgs; [
    # Desktop apps
    dunst # notifications
    firefox
    ghostty
    waybar # status bar
    wofi # app launcher

    # Gaming
    mangohud
    protonup-qt
    lutris
    bottles
    heroic

    # Mouse configuration
    piper          # GUI for configuring gaming mice
    libratbag      # Includes ratbagctl CLI tool

    # KDE config tools
    libsForQt5.kconfig  # Includes kreadconfig5 and kwriteconfig5
    kdePackages.kconfig # Includes kreadconfig6 and kwriteconfig6
  ];
}
