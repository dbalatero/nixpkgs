{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  apps = ["sonarr" "radarr" "lidarr"];
  port = network.servicesByName.prowlarr.port;
  proxyRule = "-i ens18 -s ${network.proxy.ip}/32 -p tcp --dport ${toString port} -j nixos-fw-accept";
  settings = pkgs.writeText "prowlarr-apps.json" (builtins.toJSON {
    url = "http://127.0.0.1:${toString port}";
    configXml = "${config.services.prowlarr.dataDir}/config.xml";
    apps = lib.genAttrs apps (name: {
      implementation = lib.toUpper (builtins.substring 0 1 name) + builtins.substring 1 (-1) name;
      url = "http://127.0.0.1:${toString config.services.${name}.settings.server.port}";
      configXml = "${config.services.${name}.dataDir}/config.xml";
    });
  });
in {
  services.prowlarr = {
    enable = true;
    openFirewall = false;
    settings = {
      server = {bindaddress = "*"; inherit port;};
      # Native rotation: ten 1 MiB archives plus the active file per level.
      # No separate log database or per-job log files.
      log = {level = "info"; rotate = 10; sizeLimit = 1; dbEnabled = false;};
    };
  };

  networking.firewall.extraCommands = "iptables -A nixos-fw ${proxyRule}";
  networking.firewall.extraStopCommands = "iptables -D nixos-fw ${proxyRule} 2>/dev/null || true";

  # Read API keys only at runtime; no credentials enter the Nix store.
  # Both services log to the journal, bounded by common/nfs to 512 MiB
  # persistent / 128 MiB runtime and 14 days. Caddy rotates access logs.
  systemd.services.prowlarr-apps = {
    description = "Connect Prowlarr to the declarative Servarr applications";
    wantedBy = ["multi-user.target"];
    wants = map (name: "${name}.service") apps;
    requires = ["prowlarr.service"];
    after = map (name: "${name}.service") (apps ++ ["prowlarr"]);
    serviceConfig = {
      Type = "oneshot";
      Restart = "on-failure";
      RestartSec = 30;
      TimeoutStartSec = 300;
      UMask = "0077";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      StandardOutput = "journal";
      StandardError = "journal";
      ExecStart = "${pkgs.python3}/bin/python ${./prowlarr-apps.py} ${settings}";
    };
  };
}
