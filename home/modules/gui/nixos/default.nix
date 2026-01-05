{pkgs, ...}: {
  imports = [
    # ./hyprland  # Keeping Hyprland config available but not active
    ./kde-plasma
    # ./waybar  # KDE Plasma has its own panel
    ./apps
    ./lutris
    ./mangohud
    ../gaming
  ];

  # GPU diagnostic and info tools
  home.packages = with pkgs; [
    mesa-demos # OpenGL info (provides glxinfo)
    vulkan-tools # Vulkan info (provides vulkaninfo)
    pciutils # PCI device info (provides lspci)
  ];

  # Override Steam desktop entry to use systemd-run (which we verified works)
  xdg.dataFile."applications/steam.desktop".text = ''
    [Desktop Entry]
    Name=Steam
    Comment=Application for managing and playing games on Steam
    Exec=systemd-run --user --scope steam %U
    Icon=steam
    Terminal=false
    Type=Application
    Categories=Network;FileTransfer;Game;
    MimeType=x-scheme-handler/steam;x-scheme-handler/steamlink;
    PrefersNonDefaultGPU=true
    X-KDE-RunOnDiscreteGpu=true
  '';
}
