{lib, ...}: {
  nix.enable = false;

  # Enable sudo with Touch ID
  security.pam.services.sudo_local.touchIdAuth = true;

  homebrew = {
    enable = true;
    onActivation.cleanup = "zap";

    brews = [
      "nodenv"
      "node-build"
    ];

    casks = [
      "1password-cli"
      "bartender"
      "fantastical"
      "google-chrome"
      "ghostty"
      "hammerspoon"
      "monitorcontrol"
      "karabiner-elements"
      "slack"
      "spotify"
      "vlc"
    ];
  };

  # Necessary for using flakes on this system
  nix.settings.experimental-features = "nix-command flakes";

  # Primary user for system defaults
  system = {
    # Used for backwards compatibility
    stateVersion = 5;

    primaryUser = lib.mkDefault "dbalatero";

    # Set Git commit hash for darwin-version
    configurationRevision = null;

    keyboard = {
      enableKeyMapping = true;
      remapCapsLockToControl = true;
    };

    defaults = {
      controlcenter = {
        Bluetooth = true; # Show in menu bar
      };

      dock = {
        autohide-delay = 0.0;
        autohide-time-modifier = 0.25;
        autohide = true;
        expose-animation-duration = 0.0;
        launchanim = false;
        magnification = true;
        mouse-over-hilite-stack = true; # Enable highlight hover effect for the grid view of a stack (Dock)
        orientation = "left";
        show-process-indicators = true;
        show-recents = false;
        static-only = true;

        # Disable hot corners (disabled = 1)
        wvous-tl-corner = 1;
        wvous-tr-corner = 1;
        wvous-bl-corner = 1;
        wvous-br-corner = 1;
      };

      finder = {
        AppleShowAllExtensions = true;
        AppleShowAllFiles = true;
        CreateDesktop = false; # remove all desktop icons
        FXEnableExtensionChangeWarning = false;
        FXPreferredViewStyle = "Nlsv"; # View files as list
        QuitMenuItem = true; # Allow quitting Finder via ⌘ + Q; doing so will also hide desktop icons
        ShowPathbar = true;
        ShowStatusBar = true;
        _FXShowPosixPathInTitle = true; # Display full POSIX path as Finder window title
      };

      screencapture = {
        # Disable shadow in screenshots
        disable-shadow = true;
      };

      screensaver = {
        askForPassword = true;
        askForPasswordDelay = 5; # how many seconds to wait until requiring?
      };

      LaunchServices = {
        # Disable the “Are you sure you want to open this application?” dialog
        LSQuarantine = false;
      };

      CustomSystemPreferences = {
        "com.apple.Safari" = {
          IncludeInternalDebugMenu = true;
        };

        "com.apple.TimeMachine" = {
          # Prevent Time Machine from prompting to use new hard drives as backup volume
          DoNotOfferNewDisksForBackup = true;
        };

        "com.apple.dock" = {
          # defaults write com.apple.dock no-bouncing -bool TRUE
          no-bouncing = true;
        };
      };

      NSGlobalDomain = {
        AppleShowAllExtensions = true;

        # Fastest key repeat (as exposed by system settings panel)
        KeyRepeat = 2;
        InitialKeyRepeat = 15;
        ApplePressAndHoldEnabled = false; # disable hold to bring up accent letters

        # Enable full keyboard access for all controls (e.g. enable Tab in modal dialogs)
        AppleKeyboardUIMode = 3;

        # Enable subpixel font rendering on non-Apple LCDs
        AppleFontSmoothing = 2;

        # Always show scrollbars
        AppleShowScrollBars = "Always";

        # Disable auto-correct
        NSAutomaticSpellingCorrectionEnabled = false;

        # Disable period substitution on double-space
        NSAutomaticPeriodSubstitutionEnabled = false;

        # Expand save panel by default
        NSNavPanelExpandedStateForSaveMode = true;

        # Display ASCII control characters using caret notation in standard text views
        # Try e.g. `cd /tmp; unidecode "\x{0000}" > cc.txt; open -e cc.txt`
        NSTextShowsControlCharacters = true;

        # smooth scrolling
        NSScrollAnimationEnabled = false;

        # Increase window resize speed for Cocoa applications
        NSWindowResizeTime = 0.001;

        # Disable opening and closing window animations
        NSAutomaticWindowAnimationsEnabled = false;

        # Expand print panel by default
        PMPrintingExpandedStateForPrint = true;

        # Tracking Speed
        # 0: Slow
        # 3: Fast
        "com.apple.trackpad.scaling" = 3.0;

        "com.apple.sound.beep.feedback" = 0;

        # Don't use the function keys as F1-F12, hold Fn + function key
        "com.apple.keyboard.fnState" = false;
      };
    };
  };
}
