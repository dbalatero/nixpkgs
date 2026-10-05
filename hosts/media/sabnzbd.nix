{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  service = network.servicesByName.sabnzbd;
  root = "/mnt/warez/usenet";
  python = pkgs.python3.withPackages (p: [p.configobj]);
  categories = {
    "*" = "Uncategorized";
    prowlarr = "Uncategorized";
    audio = "Audio";
    books = "Books";
    comics = "Comics";
    movie = "Movies";
    music = "Music";
    software = "Software";
    tv = "TV Shows";
  };
  proxyRule = "-i ens18 -s ${network.proxy.ip}/32 -p tcp --dport ${toString service.port} -j nixos-fw-accept";
  settings = pkgs.writeText "usenet-integrations.json" (builtins.toJSON {
    indexerPriority = 35;
    sab = {url = "http://127.0.0.1:${toString service.port}"; port = service.port;};
    prowlarr = {
      url = "http://127.0.0.1:${toString config.services.prowlarr.settings.server.port}/api/v1";
      credential = "prowlarr.xml";
    };
    apps = lib.genAttrs ["sonarr" "radarr" "lidarr"] (name: {
      url = "http://127.0.0.1:${toString config.services.${name}.settings.server.port}/api/${if name == "lidarr" then "v1" else "v3"}";
      credential = "${name}.xml";
      category = {sonarr = "tv"; radarr = "movie"; lidarr = "music";}.${name};
    });
  });
in {
  services.sabnzbd = {
    enable = true;
    configFile = null;
    # SABnzbd persists runtime state in its INI. Merge Nix settings and secrets
    # over that state on every start, then let the service write its 0600 file.
    allowConfigWrite = true;
    user = "dbalatero";
    group = "media";
    openFirewall = false;
    secretFiles = ["/run/sabnzbd/secrets.ini"];
    settings = {
      misc = {
        host = "0.0.0.0";
        port = service.port;
        host_whitelist = [service.fqdn "localhost"];
        # Browser authentication is supplied by Caddy/Authentik. The backend
        # firewall admits only Caddy; local API clients still need an API key.
        local_ranges = ["127.0.0.1/32" "${network.proxy.ip}/32"];
        # Caddy authenticates browser users. Check the trusted TCP peer rather
        # than rejecting their forwarded IP, which is outside local_ranges.
        verify_xff_header = false;
        inet_exposure = "none";
        api_warnings = true;
        download_dir = "${root}/incomplete";
        complete_dir = "${root}/complete";
        admin_dir = "/var/lib/sabnzbd/admin";
        log_dir = "/var/lib/sabnzbd/logs";
        nzb_backup_dir = "";
        backup_for_duplicates = false;
        download_free = "100G";
        complete_free = "100G";
        permissions = "0770";
        cache_limit = "512M";
        bandwidth_max = "93750000"; # 750 Mbps, independent of torrent limit.
        bandwidth_perc = 100;
        enable_https_verification = true;
        # The daily retention service expires terminal history after 30 days
        # without touching downloaded files or active jobs.
        history_retention_option = "all";
      };
      logging = {log_level = 1; max_log_size = 10485760; log_backups = 5;};
      servers.Eweka = {
        name = "Eweka";
        displayname = "Eweka";
        host = "news.eweka.nl";
        port = 563;
        ssl = true;
        ssl_verify = "strict";
        connections = 20;
        expire_date = ""; # Avoid serializing the module default null as a date.
        required = true;
      };
      categories = lib.mapAttrs (_: directory: {
        dir = directory;
        pp = "3"; # Repair, unpack, and remove redundant archives.
        script = "None";
        priority = 0;
      }) categories;
    };
  };

  systemd.services.usenet-directories = {
    description = "Create Usenet directories on the verified NAS export";
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    serviceConfig = {Type = "oneshot"; RemainAfterExit = true; User = "dbalatero"; Group = "media"; UMask = "0007";};
    path = [pkgs.coreutils pkgs.util-linux];
    script = ''
      test "$(findmnt -n -t nfs4 -T /mnt/warez -o SOURCE)" = 'truenas.vm.netcat.cloud:/mnt/warez/data'
      mkdir -p ${root}/incomplete ${root}/complete ${lib.escapeShellArgs (map (dir: "${root}/complete/${dir}") (lib.unique (lib.attrValues categories)))}
    '';
  };
  systemd.services.sabnzbd = {
    requires = ["usenet-directories.service"];
    after = ["usenet-directories.service" "network-online.target"];
    wants = ["network-online.target"];
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    preStart = lib.mkBefore ''
      ${python}/bin/python ${./sabnzbd-secrets.py}
    '';
    serviceConfig = {
      # Keep the process in the foreground so systemd tracks and restarts it.
      Type = lib.mkForce "simple";
      ExecStart = lib.mkForce "${lib.getExe config.services.sabnzbd.package} -f /var/lib/sabnzbd/sabnzbd.ini --console";
      Restart = "on-failure";
      RestartSec = 10;
      LoadCredential = ["usenet:/etc/usenet/credentials.json"];
      RuntimeDirectory = "sabnzbd";
      RuntimeDirectoryMode = "0700";
      StateDirectoryMode = "0700";
      UMask = "0007";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      NoNewPrivileges = true;
      ReadWritePaths = [root];
      StandardOutput = "journal";
      StandardError = "journal";
    };
  };
  # Music imports copy across sandbox mounts; allow cleanup of Usenet sources.
  systemd.services.lidarr = {
    requires = ["usenet-directories.service"];
    after = ["usenet-directories.service"];
    serviceConfig.ReadWritePaths = ["${root}/complete/Music"];
  };

  networking.firewall.extraCommands = "iptables -A nixos-fw ${proxyRule}";
  networking.firewall.extraStopCommands = "iptables -D nixos-fw ${proxyRule} 2>/dev/null || true";

  systemd.services.usenet-integrations = {
    description = "Configure SABnzbd clients and NinjaCentral through Servarr APIs";
    wantedBy = ["multi-user.target"];
    requires = ["sabnzbd.service" "prowlarr-apps.service" "media-api-credentials.service"];
    after = ["sabnzbd.service" "prowlarr-apps.service" "media-api-credentials.service"];
    serviceConfig = {
      Type = "oneshot";
      Restart = "on-failure";
      RestartSec = 60;
      TimeoutStartSec = 300;
      LoadCredential = ["usenet:/etc/usenet/credentials.json" "sab-api:/var/lib/sabnzbd/api-key"
        "prowlarr.xml:${config.services.prowlarr.dataDir}/config.xml"]
        ++ map (name: "${name}.xml:${config.services.${name}.dataDir}/config.xml") ["sonarr" "radarr" "lidarr"];
      ExecStart = "${pkgs.python3}/bin/python ${./usenet-configure.py} ${settings}";
      UMask = "0077";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      NoNewPrivileges = true;
    };
  };

  # Journal: common/nfs caps 512 MiB persistent / 128 MiB runtime, 14 days.
  # SABnzbd rotates its own logs at 10 MiB with five backups per log stream.
  # Job reports (including failed jobs) expire after 30 days via the API; this
  # is age-based, not a disk quota. Downloaded data and queued jobs are retained.
  systemd.services.sabnzbd-history-retention = {
    description = "Expire old SABnzbd job reports without deleting downloads";
    requires = ["sabnzbd.service"];
    after = ["sabnzbd.service"];
    serviceConfig = {
      Type = "oneshot";
      LoadCredential = ["sab-api:/var/lib/sabnzbd/api-key"];
      ExecStart = "${pkgs.python3}/bin/python ${./usenet-configure.py} ${settings} --retain-history";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      NoNewPrivileges = true;
      TimeoutStartSec = 300;
    };
  };
  systemd.timers.sabnzbd-history-retention = {
    wantedBy = ["timers.target"];
    timerConfig = {OnCalendar = "daily"; Persistent = true; RandomizedDelaySec = "10m";};
  };
}
