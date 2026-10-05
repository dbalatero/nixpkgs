{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  apps = ["sonarr" "radarr" "lidarr"];
  settings = pkgs.writeText "plex-notifications.json" (builtins.toJSON {
    host = "127.0.0.1";
    port = network.servicesByName.plex.port;
    plexPreferences = "${config.services.plex.dataDir}/Plex Media Server/Preferences.xml";
    apps = lib.genAttrs apps (name: {
      url = "http://127.0.0.1:${toString config.services.${name}.settings.server.port}/api/${if name == "lidarr" then "v1" else "v3"}";
      events = if name == "lidarr"
        then ["onReleaseImport" "onUpgrade" "onRename" "onTrackRetag"]
        else ["onDownload" "onUpgrade" "onRename"];
    });
  });
in {
  systemd.services.plex-notifications = {
    description = "Reconcile Servarr Plex library update connections";
    wantedBy = ["multi-user.target"];
    requires = map (name: "${name}.service") (apps ++ ["plex"]);
    after = map (name: "${name}.service") (apps ++ ["plex"]);
    serviceConfig = {
      Type = "oneshot";
      Restart = "on-failure";
      RestartSec = 60;
      TimeoutStartSec = 180;
      LoadCredential = map (name: "${name}.xml:${config.services.${name}.dataDir}/config.xml") apps;
      ExecStart = "${pkgs.python3}/bin/python ${./plex-notifications.py} ${settings}";
      UMask = "0077";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      NoNewPrivileges = true;
      # Only journal output: common/nfs bounds it to 512 MiB persistent,
      # 128 MiB runtime and 14 days. No file or per-job logs are created.
      StandardOutput = "journal";
      StandardError = "journal";
    };
  };
}
