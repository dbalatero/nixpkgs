{
  config,
  lib,
  pkgs,
  ...
}: {
  # Install audio control tools
  home.packages = with pkgs; [
    pwvucontrol # Modern PipeWire volume control GUI
    wireplumber # Includes wpctl for CLI control
  ];

  # Cursor theme
  home.pointerCursor = {
    gtk.enable = true;
    x11.enable = true;
    package = pkgs.bibata-cursors;
    name = "Bibata-Modern-Classic";
    size = 24;
  };

  # Set environment variables for KDE
  home.sessionVariables = {
    XCURSOR_SIZE = "24";
    XCURSOR_THEME = "Bibata-Modern-Classic";
  };

  # KDE Plasma configuration via plasma-manager
  programs.plasma = {
    enable = true;

    # Configure the desktop with a top panel
    workspace = {
      # Set wallpaper (optional - remove if you want to choose your own)
      # wallpaper = "${pkgs.kdePackages.plasma-workspace-wallpapers}/share/wallpapers/Kay/contents/images/1080x1920.png";
    };

    panels = [
      # Top panel with standard layout
      {
        location = "top";
        height = 32;
        widgets = [
          # Application launcher on the left
          {
            name = "org.kde.plasma.kickoff";
            config = {
              General = {
                icon = "nix-snowflake";
              };
            };
          }

          # Task manager in the middle (shows open apps)
          {
            name = "org.kde.plasma.icontasks";
            config = {
              General = {
                launchers = [];
              };
            };
          }

          # Spacer to push system tray to the right
          "org.kde.plasma.panelspacer"

          # System tray
          {
            systemTray.items = {
              shown = [
                "org.kde.plasma.networkmanagement"
                "org.kde.plasma.volume"
                "org.kde.plasma.bluetooth"
              ];
              hidden = [];
            };
          }

          # Digital clock
          {
            digitalClock = {
              calendar.firstDayOfWeek = "sunday";
              time.format = "24h";
            };
          }
        ];
      }
    ];

    # Configure some nice defaults
    configFile = {
      kwinrc = {
        Desktops = {
          Number = 4;
          Rows = 1;
        };
      };

      # Keyboard repeat settings
      kcminputrc = {
        Keyboard = {
          RepeatDelay = 200; # Delay before repeat starts (ms)
          RepeatRate = 33; # Repeat rate (repeats per second)
        };

        Mouse = {
          XLbInptPointerAcceleration = 3.0; # Mouse speed multiplier (default is 1.0)
          XLbInptAccelProfileFlat = false; # Use acceleration curve
        };
      };
    };

    # Keyboard shortcuts (Meta = Super = Windows key)
    shortcuts = {
      "kwin"."Window Maximize" = "Meta+Up";
      "kwin"."Switch to Desktop 1" = "Meta+1";
      "kwin"."Switch to Desktop 2" = "Meta+2";
      "kwin"."Switch to Desktop 3" = "Meta+3";
      "kwin"."Switch to Desktop 4" = "Meta+4";
    };
  };
}
