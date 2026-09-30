{lib, ...}: {
  # Leave port 53 to Pi-hole while keeping resolved for host DNS resolution.
  services.resolved.settings.Resolve.DNSStubListener = "no";
  environment.etc."resolv.conf".source = lib.mkForce "/run/systemd/resolve/resolv.conf";

  services.pihole-ftl = {
    enable = true;
    openFirewallDNS = true;
    openFirewallWebserver = true;

    settings = {
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

  services.pihole-web = {
    enable = true;
    ports = [3000];
  };
}
