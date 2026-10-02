{config, lib, pkgs, ...}: let
  python = pkgs.python3.withPackages (p: [p.guessit]);
  importer = pkgs.stdenvNoCC.mkDerivation {
    pname = "media-import";
    version = "1";
    src = ../../tools/media_import;
    dontBuild = true;
    nativeBuildInputs = [pkgs.makeWrapper];
    installPhase = ''
      mkdir -p $out/lib/media_import $out/bin
      cp *.py $out/lib/media_import/
      makeWrapper ${python}/bin/python $out/bin/media-import \
        --add-flags "-m media_import.cli" \
        --set PYTHONPATH $out/lib \
        --prefix PATH : ${lib.makeBinPath [pkgs.ffmpeg pkgs._7zz pkgs.util-linux]}
    '';
  };
  state = "/var/lib/media-import";
  media = "/mnt/warez/media";
  apps = ["sonarr" "radarr" "lidarr"];
  policy = {
    "config/mediamanagement" = {
      copyUsingHardlinks = true;
      setPermissionsLinux = false;
      importExtraFiles = false;
      deleteEmptyFolders = false;
      fileDate = "none";
      rescanAfterRefresh = "afterManual";
    };
  };
  dataDirs = {
    sonarr = config.services.sonarr.dataDir;
    radarr = config.services.radarr.dataDir;
    lidarr = config.services.lidarr.dataDir;
  };
  serviceGuard = {
    requires = ["media-library-directories.service"];
    after = ["media-library-directories.service"];
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
  };
  arrGuard = serviceGuard // {
    serviceConfig = {
      PrivateUsers = lib.mkForce false;
      UMask = lib.mkForce "0007";
      ReadOnlyPaths = ["/mnt/warez"];
    };
  };
in {
  environment.systemPackages = [importer pkgs.sqlite pkgs.ffmpeg pkgs.acl];

  environment.etc."media-import.json".text = builtins.toJSON {
    database = "${state}/audit.sqlite";
    source = "/mnt/warez/torrents";
    inherit media;
    localBackups = "${state}/backups";
    nasBackups = "/mnt/warez/media-import-audit";
    stabilitySeconds = 600;
    mount = {
      source = "truenas.vm.netcat.cloud:/mnt/warez/data";
      target = "/mnt/warez";
    };
    apps = lib.genAttrs apps (name: {
      url = "http://127.0.0.1:${toString config.services.${name}.settings.server.port}/api/${if name == "lidarr" then "v1" else "v3"}";
      configXml = "${dataDirs.${name}}/config.xml";
      keyFile = "${state}/${name}.key";
    }) // {
      audiobookshelf = {
        url = "http://127.0.0.1:8000/api";
        keyFile = "${state}/audiobookshelf.token";
        bearer = true;
      };
    };
    policy = {
      sonarr = policy;
      radarr = policy // {
        "config/mediamanagement" = policy."config/mediamanagement" // {autoRenameFolders = false;};
      };
      lidarr = policy // {
        "config/mediamanagement" = policy."config/mediamanagement" // {watchLibraryForChanges = false;};
        "config/metadataprovider" = {
          writeAudioTags = "no";
          scrubAudioTags = false;
          embedCoverArt = false;
        };
      };
    };
  };

  services.sonarr.enable = true;
  services.radarr.enable = true;
  services.lidarr.enable = true;
  services.audiobookshelf = {
    enable = true;
    host = "127.0.0.1";
    openFirewall = false;
  };
  services.sonarr.settings.server.bindaddress = "127.0.0.1";
  services.radarr.settings.server.bindaddress = "127.0.0.1";
  services.lidarr.settings.server.bindaddress = "127.0.0.1";

  users.users = lib.genAttrs (apps ++ ["audiobookshelf"]) (_: {extraGroups = ["media"];});
  systemd.tmpfiles.rules = [
    "d ${state} 0700 dbalatero media -"
    "d ${state}/backups 0700 dbalatero media -"
  ];

  # NAS directories are created as the existing NAS owner after a real mount
  # check. Never use boot-time tmpfiles rules underneath an automount.
  systemd.services.media-library-directories = {
    description = "Create media roots on the verified NAS export";
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = "dbalatero";
      Group = "media";
      UMask = "0007";
    };
    path = [pkgs.util-linux pkgs.coreutils];
    script = ''
      test -d /mnt/warez/torrents
      test "$(findmnt -n -t nfs4 -T /mnt/warez/torrents -o SOURCE)" = 'truenas.vm.netcat.cloud:/mnt/warez/data'
      mkdir -p ${media}/{movies,tv,music,audiobooks,spoken-word,alternates} /mnt/warez/media-import-audit
      chmod 2770 ${media} ${media}/{movies,tv,music,audiobooks,spoken-word,alternates}
    '';
  };

  systemd.services = {
    sonarr = arrGuard;
    radarr = arrGuard;
    lidarr = arrGuard;
    audiobookshelf = serviceGuard // {
      serviceConfig.ReadOnlyPaths = ["/mnt/warez"];
    };
    media-import-configure = {
      description = "Apply declarative migration safety policy through Servarr APIs";
      wantedBy = ["multi-user.target"];
      after = map (name: "${name}.service") (apps ++ ["audiobookshelf"]);
      requires = map (name: "${name}.service") (apps ++ ["audiobookshelf"]);
      serviceConfig = {
        Type = "oneshot";
        Restart = "on-failure";
        RestartSec = 15;
        TimeoutStartSec = 180;
      };
      script = ''
        # Apps create their config files asynchronously on first start.
        for attempt in $(seq 1 30); do
          if test -f ${dataDirs.sonarr}/config.xml && test -f ${dataDirs.radarr}/config.xml && test -f ${dataDirs.lidarr}/config.xml; then
            break
          fi
          sleep 1
        done
        ${python}/bin/python - <<'PY'
        import json, os, xml.etree.ElementTree as ET
        from pathlib import Path
        settings = json.loads(Path('/etc/media-import.json').read_text())
        for name in ('sonarr', 'radarr', 'lidarr'):
          app = settings['apps'][name]
          key = ET.parse(app['configXml']).getroot().findtext('ApiKey')
          if not key:
            raise SystemExit('Application API key not initialized')
          path = Path(app['keyFile'])
          path.write_text(key)
          os.chmod(path, 0o600)
          os.chown(path, 1000, 2000)
        PY
        for attempt in $(seq 1 12); do
          if ${pkgs.util-linux}/bin/runuser -u dbalatero -- ${importer}/bin/media-import configure; then
            exit 0
          fi
          sleep 5
        done
        exit 1
      '';
    };
    media-import-audit-backup = serviceGuard // {
      description = "Back up the media audit database to the NAS";
      serviceConfig = {
        Type = "oneshot";
        User = "dbalatero";
        Group = "media";
        ExecStart = "${importer}/bin/media-import backup";
      };
    };
  };
  systemd.timers.media-import-audit-backup = {
    wantedBy = ["timers.target"];
    timerConfig = {OnCalendar = "daily"; Persistent = true;};
  };

  # Native NLog rotation: ten 1 MiB archives plus the active file per level.
  # Disable the separate log database; journals and rotating files retain logs.
  services.sonarr.settings.log = {level = "info"; rotate = 10; sizeLimit = 1; dbEnabled = false;};
  services.radarr.settings.log = {level = "info"; rotate = 10; sizeLimit = 1; dbEnabled = false;};
  services.lidarr.settings.log = {level = "info"; rotate = 10; sizeLimit = 1; dbEnabled = false;};
  # ABS daily/scan logs are closed per job/day. Age-based retention is not a
  # strict byte quota. Never clean its metadata or backup directories here.
  systemd.services.media-log-retention = {
    serviceConfig.Type = "oneshot";
    path = [pkgs.findutils];
    script = ''
      if test -d /var/lib/audiobookshelf/metadata/logs; then
        find /var/lib/audiobookshelf/metadata/logs -type f -name '*.txt' ! -name crash_logs.txt -mtime +14 -delete
      fi
    '';
  };
  systemd.timers.media-log-retention = {
    wantedBy = ["timers.target"];
    timerConfig = {OnCalendar = "daily"; Persistent = true;};
  };
  services.logrotate.settings.audiobookshelf-crash = {
    files = ["/var/lib/audiobookshelf/metadata/logs/crash_logs.txt"];
    frequency = "daily";
    maxsize = "10M";
    rotate = 7;
    compress = true;
    missingok = true;
    notifempty = true;
    # Crash records are appended via discrete filesystem writes, not a held FD.
    create = "0600 audiobookshelf audiobookshelf";
  };
}
