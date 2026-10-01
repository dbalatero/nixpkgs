{lib, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  homepage = network.servicesByName.homepage;
in {
  services.homepage-dashboard = {
    enable = true;
    listenPort = homepage.port;
    allowedHosts = homepage.fqdn;
    openFirewall = false;
    settings.title = "Hello World";
  };

  systemd.services.homepage-dashboard.environment = {
    HOSTNAME = "127.0.0.1";
    # No application log files; journald owns retention.
    LOG_TARGETS = "stdout";
  };
  # Bounds Homepage and Caddy runtime logs; journald handles cleanup internally.
  services.journald.extraConfig = ''
    SystemMaxUse=512M
    RuntimeMaxUse=128M
    MaxRetentionSec=14day
  '';
}
