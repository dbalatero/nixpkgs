{
  config,
  lib,
  pkgs,
  ...
}: {
  # Install BlueBubbles via Flatpak (using nix-flatpak)
  # BlueBubbles is an iMessage client that connects to a BlueBubbles server
  # Server URL: http://192.168.1.209:1234

  # Note: Flatpak is enabled at the system level in hosts/common/desktop/default.nix
  services.flatpak = {
    packages = [
      "app.bluebubbles.BlueBubbles"
    ];
  };

  # Note: After first login, configure the server:
  # 1. Launch BlueBubbles from your application menu
  # 2. Enter server URL: http://192.168.1.209:1234
  # 3. Enter the password from your BlueBubbles server
}
