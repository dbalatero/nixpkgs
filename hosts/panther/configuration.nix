# Edit this configuration file to define what should be installed on
# your system. Help is available in the configuration.nix(5) man page, on
# https://search.nixos.org/options and in the NixOS manual (`nixos-help`).
{
  config,
  lib,
  pkgs,
  ...
}: {
  imports = [
    # Include the results of the hardware scan.
    ./hardware-configuration.nix
  ];

  boot.loader = {
    efi.canTouchEfiVariables = true;

    grub = {
      enable = true;
      device = "nodev";
      efiSupport = true;
      useOSProber = true; # detect windows disk partition
    };
  };

  # Use latest kernel.
  boot.kernelPackages = pkgs.linuxPackages_latest;

  # AMD GPU configuration
  hardware.graphics = {
    enable = true;
    enable32Bit = true; # Required for Steam

    # Extra packages for AMD GPU support
    # Note: RADV (open-source AMD Vulkan) is enabled by default
    extraPackages = with pkgs; [
      rocmPackages.clr.icd  # OpenCL support
    ];
  };

  services.xserver.videoDrivers = ["amdgpu"];

  # AMD GPU boot parameters for better performance
  boot.kernelParams = [
    "amdgpu.ppfeaturemask=0xffffffff"  # Enable all GPU features
  ];

  networking.hostName = "panther"; # Define your hostname.

  # Configure network connections interactively with nmcli or nmtui.
  networking.networkmanager.enable = true;

  # Set your time zone.
  time.timeZone = "America/New_York";

  # Configure network proxy if necessary
  # networking.proxy.default = "http://user:password@proxy:port/";
  # networking.proxy.noProxy = "127.0.0.1,localhost,internal.domain";

  # Select internationalisation properties.
  i18n.defaultLocale = "en_US.UTF-8";

  i18n.extraLocaleSettings = {
    LC_ADDRESS = "en_US.UTF-8";
    LC_IDENTIFICATION = "en_US.UTF-8";
    LC_MEASUREMENT = "en_US.UTF-8";
    LC_MONETARY = "en_US.UTF-8";
    LC_NAME = "en_US.UTF-8";
    LC_NUMERIC = "en_US.UTF-8";
    LC_PAPER = "en_US.UTF-8";
    LC_TELEPHONE = "en_US.UTF-8";
    LC_TIME = "en_US.UTF-8";
  };

  # console = {
  #   font = "Lat2-Terminus16";
  #   keyMap = "us";
  #   useXkbConfig = true; # use xkb.options in tty.
  # };

  # Enable the X11 windowing system (required even for Wayland desktop environments)
  services.xserver.enable = true;

  # Configure keymap in X11
  # services.xserver.xkb.layout = "us";
  # services.xserver.xkb.options = "eurosign:e,caps:escape";

  # Enable CUPS to print documents.
  # services.printing.enable = true;

  # Enable sound.
  # services.pulseaudio.enable = true;
  # OR
  # services.pipewire = {
  #   enable = true;
  #   pulse.enable = true;
  # };

  # Enable touchpad support (enabled default in most desktopManager).
  # services.libinput.enable = true;

  # Define a user account. Don't forget to set a password with ‘passwd’.
  # users.users.alice = {
  #   isNormalUser = true;
  #   extraGroups = [ "wheel" ]; # Enable ‘sudo’ for the user.
  #   packages = with pkgs; [
  #     tree
  #   ];
  # };

  # programs.firefox.enable = true;

  # Hyprland (keeping available but not active)
  # programs.hyprland = {
  #   enable = true;
  #   xwayland.enable = true;
  # };

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

  # Enable zsh system-wide (required when setting user shell to zsh)
  programs.zsh.enable = true;

  # Steam
  programs.steam = {
    enable = true;
    remotePlay.openFirewall = true;
    dedicatedServer.openFirewall = true;
    # gamescopeSession.enable = true; # Disabled - trying without it

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
            # Remap capslock to control (hold) or enter (tap)
            capslock = "overload(control, enter)";
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

  # greetd login manager (used with Hyprland, not needed with SDDM)
  # services.greetd = {
  #   enable = true;
  #   settings = {
  #     default_session = {
  #       command = "${pkgs.tuigreet}/bin/tuigreet --time --cmd hyprland";
  #     };
  #   };
  # };

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

  # Allow wheel group to use sudo without password
  security.sudo.wheelNeedsPassword = false;

  # List packages installed in system profile.
  # You can use https://search.nixos.org/ to find more packages (and options).
  environment.systemPackages = with pkgs; [
    dunst # notifications
    firefox
    ghostty
    git
    neovim
    vim
    waybar # status bar
    wget
    wofi # app launcher

    # Gaming
    mangohud
    protonup-qt
    lutris
    bottles
    heroic

    # AMD GPU utilities
    radeontop      # GPU monitoring tool
    clinfo         # OpenCL info
    vulkan-tools   # Vulkan utilities (vulkaninfo, etc.)
    lshw           # Hardware info

    # Mouse configuration
    piper          # GUI for configuring gaming mice
    libratbag      # Includes ratbagctl CLI tool

    # KDE config tools
    libsForQt5.kconfig  # Includes kreadconfig5 and kwriteconfig5
  ];

  # Some programs need SUID wrappers, can be configured further or are
  # started in user sessions.
  # programs.mtr.enable = true;
  # programs.gnupg.agent = {
  #   enable = true;
  #   enableSSHSupport = true;
  # };

  # List services that you want to enable:

  # Enable the OpenSSH daemon.
  # services.openssh.enable = true;

  # Open ports in the firewall.
  # networking.firewall.allowedTCPPorts = [ ... ];
  # networking.firewall.allowedUDPPorts = [ ... ];
  # Or disable the firewall altogether.
  # networking.firewall.enable = false;

  # Copy the NixOS configuration file and link it from the resulting system
  # (/run/current-system/configuration.nix). This is useful in case you
  # accidentally delete configuration.nix.
  # system.copySystemConfiguration = true;

  # This option defines the first version of NixOS you have installed on this particular machine,
  # and is used to maintain compatibility with application data (e.g. databases) created on older NixOS versions.
  #
  # Most users should NEVER change this value after the initial install, for any reason,
  # even if you've upgraded your system to a new NixOS release.
  #
  # This value does NOT affect the Nixpkgs version your packages and OS are pulled from,
  # so changing it will NOT upgrade your system - see https://nixos.org/manual/nixos/stable/#sec-upgrading for how
  # to actually do that.
  #
  # This value being lower than the current NixOS release does NOT mean your system is
  # out of date, out of support, or vulnerable.
  #
  # Do NOT change this value unless you have manually inspected all the changes it would make to your configuration,
  # and migrated your data accordingly.
  #
  # For more information, see `man configuration.nix` or https://nixos.org/manual/nixos/stable/options#opt-system.stateVersion .
  system.stateVersion = "25.11"; # Did you read the comment?
}
