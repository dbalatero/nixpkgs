{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  port = network.servicesByName.seerr.port;
  apps = ["sonarr" "radarr"];
  proxyRule = "-i ens18 -s ${network.proxy.ip}/32 -p tcp --dport ${toString port} -j nixos-fw-accept";
  settings = pkgs.writeText "seerr-defaults.json" (builtins.toJSON {
    applicationUrl = "https://${network.servicesByName.seerr.fqdn}";
    # REQUEST | AUTO_APPROVE; users receive no administrative/advanced access.
    defaultPermissions = 160;
    apps = lib.genAttrs apps (name: {
      hostname = "127.0.0.1";
      port = config.services.${name}.settings.server.port;
      externalUrl = "https://${network.servicesByName.${name}.fqdn}";
      root = "/mnt/warez/media/${if name == "radarr" then "movies" else "tv"}";
      qualityProfile = "HD-1080p";
    });
  });
in {
  services.seerr = {
    enable = true;
    inherit port;
    configDir = "/var/lib/seerr";
    openFirewall = false;
  };
  networking.firewall.extraCommands = "iptables -A nixos-fw ${proxyRule}";
  networking.firewall.extraStopCommands = "iptables -D nixos-fw ${proxyRule} 2>/dev/null || true";
  systemd.services.seerr = {
    description = lib.mkForce "Seerr movie and TV requests for Plex";
    wants = map (name: "${name}.service") apps;
    after = map (name: "${name}.service") apps;
    environment.LOG_LEVEL = "info";
    serviceConfig = {
      StateDirectory = lib.mkForce "seerr";
      StateDirectoryMode = "0700";
      UMask = "0077";
      TimeoutStartSec = 300;
      RestartSec = 15;
      LoadCredential = map (name: "${name}.xml:${config.services.${name}.dataDir}/config.xml") apps;
    };
    # Merge only owned defaults while stopped, preserving accounts, sessions,
    # Plex authentication, and unrelated settings. Secrets are read at runtime.
    preStart = ''
      ${pkgs.python3}/bin/python ${./seerr-configure.py} ${settings}
    '';
  };
  # Seerr 3.3.0's native Winston rotation compresses 20 MiB segments and retains
  # human logs for seven days, machine logs for one day. This is age-based,
  # not a strict aggregate disk quota. No external rotation of open files.
  # Console/setup logs use common/nfs's 512 MiB / 128 MiB / 14-day journal cap.
}
