{lib, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  homepage = network.servicesByName.homepage;
in {
  services.homepage-dashboard = {
    enable = true;
    listenPort = homepage.port;
    allowedHosts = homepage.fqdn;
    openFirewall = false;
    settings = {
      title = "netcat homelab";
      description = "Infrastructure and markets, at a glance.";
      theme = "dark";
      color = "slate";
      headerStyle = "clean";
      useEqualHeights = true;
      hideVersion = true;
      disableCollapse = true;
      layout = {
        Infrastructure = {style = "row"; columns = 2;};
        Markets = {style = "row"; columns = 1;};
      };
      providers.finnhub = "{{HOMEPAGE_VAR_FINNHUB_API_KEY}}";
    };
    widgets = [
      {greeting = {text = "netcat homelab"; text_size = "3xl";};}
      {datetime = {
        text_size = "sm";
        format = {dateStyle = "medium"; timeStyle = "short"; hour12 = false;};
      };}
    ];
    customCSS = builtins.readFile ./homepage.css;
    environmentFiles = ["/etc/homepage-dashboard.env"];
    services = [{
      Infrastructure = [{
        Proxmox = {
          icon = "mdi-server-network";
          description = "Compute / virtual machines";
          href = "https://${network.servicesByName.proxmox.fqdn}/";
          widget = {
            type = "proxmox";
            url = "https://${network.servicesByName.proxmox.fqdn}";
            username = "{{HOMEPAGE_VAR_PROXMOX_TOKEN_ID}}";
            password = "{{HOMEPAGE_VAR_PROXMOX_TOKEN_SECRET}}";
          };
        };
      } {
        "Pi-hole" = {
          icon = "mdi-shield-check-outline";
          description = "Network / DNS filtering";
          href = "https://${network.servicesByName.pihole-dns.fqdn}/admin/";
          widget = {
            type = "pihole";
            # Server-side widget requests do not have a browser SSO session.
            url = network.servicesByName.pihole-dns.upstream;
            version = 6;
            # Pi-hole currently has authentication disabled; no key is needed.
            fields = ["queries" "blocked" "blocked_percent" "gravity"];
          };
        };
      }];
    } {
      Markets = [{
        Stocks = {
          icon = "mdi-chart-line";
          description = "SPCX / market watch";
          widget = {
            type = "stocks";
            provider = "finnhub";
            showUSMarketStatus = true;
            watchlist = ["SPCX"];
          };
        };
      }];
    }];
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
