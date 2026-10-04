{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  port = network.servicesByName.qbittorrent.port;
  profile = config.services.qbittorrent.profileDir;
  categories = {
    audio = "Audio";
    books = "Books";
    comics = "Comics";
    movie = "Movies";
    music = "Music";
    software = "Software";
    tv = "TV Shows";
  };
  categoryFile = pkgs.writeText "torrent-categories.json" (builtins.toJSON
    (lib.mapAttrs (_: directory: {save_path = "/mnt/warez/torrents/${directory}";}) categories));
  initialize = pkgs.writeShellScript "qbittorrent-initialize" ''
    set -eu
    # Inspect the export mount, not the service's writable subtree bind mount.
    test "$( ${pkgs.util-linux}/bin/findmnt -n -t nfs4 -T /mnt/warez -o SOURCE)" = 'truenas.vm.netcat.cloud:/mnt/warez/data'
    ${pkgs.python3}/bin/python ${./qbittorrent-init.py} ${profile} ${categoryFile}
  '';
  proxyRule = "-i ens18 -s ${network.proxy.ip}/32 -p tcp --dport ${toString port} -j nixos-fw-accept";
in {
  services.qbittorrent = {
    enable = true;
    # The existing NFS directories are owned by UID 1000, with NAS ACLs.
    user = "dbalatero";
    group = "media";
    webuiPort = port;
    torrentingPort = 6881;
    openFirewall = false;
    serverConfig = {
      LegalNotice.Accepted = true;
      Application.FileLogger.Enabled = false;
      BitTorrent.Session = {
        DefaultSavePath = "/mnt/warez/torrents";
        TempPathEnabled = false;
        DisableAutoTMMByDefault = false;
        DisableAutoTMMTriggers = {
          CategoryChanged = false;
          CategorySavePathChanged = false;
          DefaultSavePathChanged = false;
        };
        UseCategoryPathsInManualMode = true;
        # qBittorrent stores KiB/s: round down from decimal Mbps.
        GlobalUPSpeedLimit = 61035; # 500 Mbps
        GlobalDLSpeedLimit = 91552; # 750 Mbps
        IncludeOverheadInLimits = true;
        uTPRateLimited = true;
        UseAlternativeGlobalSpeedLimit = false;
        BandwidthSchedulerEnabled = false;
        AddExtensionToIncompleteFiles = true;
      };
      Preferences.WebUI = {
        Address = "*";
        Username = "dbalatero";
        LocalHostAuth = false;
        AuthSubnetWhitelistEnabled = true;
        AuthSubnetWhitelist = "${network.proxy.ip}/32";
        ServerDomains = "torrents.netcat.cloud";
        HostHeaderValidation = true;
        CSRFProtection = true;
        # Authenticate by the TCP peer (Caddy), not its forwarded browser IP.
        # The firewall admits only Caddy; Host and CSRF checks remain enabled.
        ReverseProxySupportEnabled = false;
        UseUPnP = false;
      };
    };
  };

  systemd.tmpfiles.rules = ["d ${profile} 0700 dbalatero media -"];
  systemd.services.qbittorrent = {
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    serviceConfig = {
      PrivateUsers = lib.mkForce false;
      UMask = "0007";
      ProtectSystem = lib.mkForce "strict";
      ReadWritePaths = [profile "/mnt/warez/torrents"];
      # Runs after the upstream module installs the declarative INI file.
      ExecStartPre = lib.mkAfter [initialize];
      StandardOutput = "journal";
      StandardError = "journal";
    };
  };

  # The web UI is reachable only through Caddy or local connections.
  networking.firewall.extraCommands = "iptables -A nixos-fw ${proxyRule}";
  networking.firewall.extraStopCommands = "iptables -D nixos-fw ${proxyRule} 2>/dev/null || true";
  networking.firewall.allowedTCPPorts = [6881];
  networking.firewall.allowedUDPPorts = [6881];

  # qBittorrent file logging is disabled; common/nfs bounds the journal to
  # 512 MiB persistent / 128 MiB runtime and 14 days, including setup jobs.
  systemd.services.media-torrent-clients = {
    description = "Configure the declarative qBittorrent clients in Servarr";
    wantedBy = ["multi-user.target"];
    requires = ["qbittorrent.service" "media-import-configure.service"];
    after = ["qbittorrent.service" "media-import-configure.service"];
    serviceConfig = {
      Type = "oneshot";
      Restart = "on-failure";
      RestartSec = 15;
      TimeoutStartSec = 180;
      ExecStart = "${pkgs.python3}/bin/python ${./torrent-clients.py}";
    };
  };
}
