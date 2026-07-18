# Panther - Gaming desktop with KDE Plasma
{
  config,
  lib,
  pkgs,
  ...
}: {
  imports = [
    # Hardware configuration
    ./hardware-configuration.nix

    # Common NixOS configuration (SSH, users, base packages, etc.)
    ../common/nixos

    # Desktop environment configuration (KDE, gaming, audio, etc.)
    ../common/desktop
  ];

  # Hostname
  networking.hostName = "panther";

  # Dedicated storage drive.
  fileSystems."/mnt/storage" = {
    device = "/dev/disk/by-label/storage";
    fsType = "ext4";
    options = [
      "nofail"
      "x-systemd.device-timeout=5s"
    ];
  };

  systemd.tmpfiles.rules = [
    "d /mnt/storage 0775 dbalatero users -"
    "d /mnt/storage/SteamLibrary 0775 dbalatero users -"
  ];

  # Keep local Nix builds from overwhelming the desktop during large nixpkgs updates.
  nix.settings = {
    experimental-features = [
      "nix-command"
      "flakes"
    ];
    max-jobs = 4;
    cores = 1;
  };

  # Panther has no disk swap configured; zram gives rebuilds a compressed memory cushion.
  zramSwap = {
    enable = true;
    memoryPercent = 50;
  };

  # Boot loader configuration
  boot.loader = {
    efi.canTouchEfiVariables = true;

    grub = {
      enable = true;
      device = "nodev";
      efiSupport = true;
    };
  };

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

  # Printing
  services.printing = {
    enable = true;
    drivers = with pkgs; [
      brlaser              # Open-source Brother laser driver
      brgenml1lpr          # Brother generic LPR driver
      brgenml1cupswrapper  # Brother generic CUPS wrapper
    ];
  };

  # Network printer discovery (Avahi/mDNS)
  services.avahi = {
    enable = true;
    nssmdns4 = true;
    openFirewall = true;
  };

  # Flipper Zero
  hardware.flipperzero.enable = true;

  # AMD GPU utilities
  environment.systemPackages = with pkgs; [
    radeontop      # GPU monitoring tool
    clinfo         # OpenCL info
    vulkan-tools   # Vulkan utilities (vulkaninfo, etc.)
    lshw           # Hardware info
    ffmpeg         # Audio/video processing

    # Printing
    system-config-printer  # KDE printer management backend

    unrar
    zip
    unzip
    flips
  ];
}
