{lib, ...}: {
  # Leave port 53 to Pi-hole while keeping resolved for host DNS resolution.
  services.resolved.settings.Resolve.DNSStubListener = "no";
  environment.etc."resolv.conf".source = lib.mkForce "/run/systemd/resolve/resolv.conf";

  services.pihole-ftl = {
    enable = true;
    openFirewallDNS = true;
    openFirewallWebserver = true;

    settings = {
      # Bound long-term query history separately from the text logs.
      database.maxDBdays = 30;

      dns = {
        upstreams = ["1.1.1.1" "8.8.8.8"];
        listeningMode = "LOCAL";
      };

      # UniFi keeps providing DHCP
      dhcp.active = false;

      # Initial LAN setup: dashboard has no password.
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
    ports = [3000];
  };
}
