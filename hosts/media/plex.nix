{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  port = network.servicesByName.plex.port;
  data = "${config.services.plex.dataDir}/Plex Media Server";
  proxyRule = "-i ens18 -s ${network.proxy.ip}/32 -p tcp --dport ${toString port} -j nixos-fw-accept";
  settings = pkgs.writeText "plex-defaults.json" (builtins.toJSON {
    dataDir = data;
    url = "http://127.0.0.1:${toString port}";
    preferences = {
      FriendlyName = "Media";
      customConnections = "https://${network.servicesByName.plex.fqdn}:443";
      # Keep Plex's automatic remote-access/port-mapping feature disabled.
      # Caddy access is controlled separately by the proxy and router firewall.
      PublishServerOnPlexOnlineKey = "0";
      # NFS does not reliably deliver inotify events; scan hourly instead.
      FSEventLibraryUpdatesEnabled = "0";
      ScheduledLibraryUpdatesEnabled = "1";
      ScheduledLibraryUpdateInterval = "3600";
      autoEmptyTrash = "0";
      allowMediaDeletion = "0";
      logDebug = "0";
      LogVerbose = "0";
      LogNumFiles = "5";
    };
    libraries = [
      {name = "Movies"; type = "movie"; agent = "tv.plex.agents.movie"; scanner = "Plex Movie"; path = "/mnt/warez/media/movies";}
      {name = "TV Shows"; type = "show"; agent = "tv.plex.agents.series"; scanner = "Plex TV Series"; path = "/mnt/warez/media/tv";}
      {name = "Music"; type = "artist"; agent = "tv.plex.agents.music"; scanner = "Plex Music"; path = "/mnt/warez/media/music";}
    ];
  });
  preferences = pkgs.writeShellScript "plex-preferences" ''
    ${pkgs.python3}/bin/python ${./plex-configure.py} ${settings} preferences
  '';
in {
  services.plex = {
    enable = true;
    openFirewall = false;
    # This VM currently has no declared GPU passthrough.
    accelerationDevices = [];
  };
  users.users.plex.extraGroups = ["media"];
  networking.firewall.extraCommands = "iptables -A nixos-fw ${proxyRule}";
  networking.firewall.extraStopCommands = "iptables -D nixos-fw ${proxyRule} 2>/dev/null || true";
  systemd.services.plex = {
    requires = ["media-library-directories.service"];
    after = ["media-library-directories.service"];
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    serviceConfig = {
      UMask = "0077";
      ReadOnlyPaths = ["/mnt/warez"];
      ExecStartPre = lib.mkAfter [preferences];
    };
  };
  # Once the owner claims Plex in their browser, create missing libraries from
  # these declarations. Never delete libraries or change existing locations.
  systemd.services.plex-libraries = {
    after = ["plex.service"];
    requires = ["plex.service"];
    serviceConfig = {
      Type = "oneshot";
      User = "plex";
      Group = "plex";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      ExecStart = "${pkgs.python3}/bin/python ${./plex-configure.py} ${settings} libraries";
    };
  };
  systemd.timers.plex-libraries = {
    wantedBy = ["timers.target"];
    timerConfig = {OnBootSec = "1min"; OnUnitInactiveSec = "1min";};
  };
  # Plex rotates its own active logs (five archives per log via LogNumFiles).
  # Plugin/job archives also get age-based cleanup, retaining current *.log
  # files. This is not a strict aggregate quota; data/caches are never removed.
  systemd.services.plex-log-retention = {
    serviceConfig = {Type = "oneshot"; User = "plex"; Group = "plex";};
    script = ''
      if test -d ${lib.escapeShellArg "${data}/Logs"}; then
        ${pkgs.findutils}/bin/find ${lib.escapeShellArg "${data}/Logs"} -type f \
          \( -name '*.log.*' -o -name '*.log.[0-9]*.gz' \) -mtime +14 -delete
      fi
    '';
  };
  systemd.timers.plex-log-retention = {
    wantedBy = ["timers.target"];
    timerConfig = {OnCalendar = "daily"; Persistent = true;};
  };
  # Console and provisioning output is bounded by common/nfs's journal policy.
}
