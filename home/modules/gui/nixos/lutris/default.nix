{
  pkgs,
  config,
  ...
}: {
  # Lutris - Multi-platform game launcher with Battle.net/Blizzard support
  # Configured with Wine dependencies for NixOS
  # See: https://nixos.wiki/wiki/Lutris
  home.packages = with pkgs; [
    # Lutris with Wine support
    (lutris.override {
      extraPkgs = pkgs: [
        # Wine with full 32/64-bit support
        wineWowPackages.stagingFull

        # Wine helper tools
        winetricks
      ];
    })
  ];

  # Symlink lutris config from repo (writable, tracked in git)
  home.file.".config/lutris/lutris.conf".source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/nixpkgs/home/modules/gui/nixos/lutris/lutris.conf";
}
