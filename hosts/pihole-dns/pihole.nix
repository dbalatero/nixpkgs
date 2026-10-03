{lib, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  webPort = network.servicesByName.pihole-dns.port;
in {
  # Only the reverse proxy may reach the dashboard/API from another machine.
  # NixOS recreates nixos-fw on reload, so this rule needs no separate cleanup.
  networking.firewall.extraCommands = ''
    iptables -w -A nixos-fw -s ${network.proxy.ip}/32 -p tcp --dport ${toString webPort} -j nixos-fw-accept
  '';

  # Leave port 53 to Pi-hole while keeping resolved for host DNS resolution.
  services.resolved.settings.Resolve.DNSStubListener = "no";
  environment.etc."resolv.conf".source = lib.mkForce "/run/systemd/resolve/resolv.conf";

  services.pihole-ftl = {
    enable = true;
    openFirewallDNS = true;
    openFirewallWebserver = false;

    settings = {
      # Bound long-term query history separately from the text logs.
      database.maxDBdays = 30;

      dns = {
        upstreams = ["1.1.1.1" "8.8.8.8"];
        listeningMode = "LOCAL";
        hosts = network.dnsHosts;
        # Unknown names in the private zone must not leak to public resolvers.
        domain = {
          name = network.domain;
          local = true;
        };
      };

      # UniFi keeps providing DHCP
      dhcp.active = false;

      # Authentication is handled by Caddy; direct remote access is restricted above.
      webserver.api.pwhash = "";
    };

    lists = [
      {
        url = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts";
        type = "block";
        enabled = true;
        description = "StevenBlack hosts";
      }
    ];
  };

  # Bound service and firewall journal logs as well as Pi-hole's text logs.
  services.journald.extraConfig = ''
    SystemMaxUse=256M
    RuntimeMaxUse=64M
    MaxRetentionSec=7day
  '';

  # Check hourly for logs exceeding 10 MiB, otherwise rotate daily.
  services.logrotate = {
    settings.pihole-ftl = {
      files = lib.mkForce [
        "/var/log/pihole/FTL.log"
        "/var/log/pihole/pihole.log"
        "/var/log/pihole/webserver.log"
      ];
      frequency = "daily";
      maxsize = "10M";
      rotate = 7;
      compress = true;
      missingok = true;
      notifempty = true;
      # Match Pi-hole's upstream rotation without restarting DNS.
      copytruncate = true;
      su = "pihole pihole";
    };
  };

  services.pihole-web = {
    enable = true;
    ports = [webPort];
  };
}
