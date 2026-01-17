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

  # Boot loader configuration
  boot.loader = {
    efi.canTouchEfiVariables = true;

    grub = {
      enable = true;
      device = "nodev";
      efiSupport = true;
      useOSProber = true; # detect windows disk partition
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

  # AMD GPU utilities
  environment.systemPackages = with pkgs; [
    radeontop      # GPU monitoring tool
    clinfo         # OpenCL info
    vulkan-tools   # Vulkan utilities (vulkaninfo, etc.)
    lshw           # Hardware info
  ];
}
