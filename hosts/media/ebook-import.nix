{config, lib, pkgs, ...}: let
  state = "/var/lib/ebook-import";
  root = "/mnt/warez/media/ebooks";
  importer = pkgs.writeShellApplication {
    name = "ebook-import";
    runtimeInputs = [pkgs.python3 pkgs._7zz];
    text = ''
      exec python ${../../tools/ebook_import.py} "$@"
    '';
  };
in {
  environment.systemPackages = [importer];
  environment.etc."ebook-import.json".text = builtins.toJSON {
    inherit state;
    source = "/mnt/warez/torrents";
    incoming = "${root}/incoming";
    outbox = "${root}/.staging";
    work = "${state}/work";
    url = "http://127.0.0.1:${toString config.services.qbittorrent.webuiPort}/api/v2";
    sevenzip = "${pkgs._7zz}/bin/7zz";
  };
  services.qbittorrent.serverConfig.AutoRun = {
    enabled = true;
    # %K supports both v1 and v2 torrents. No torrent-provided names enter a shell.
    # qBittorrent splits arguments before substituting these placeholders.
    program = "${importer}/bin/ebook-import enqueue %K %L";
  };
  systemd.services.qbittorrent.serviceConfig.ReadWritePaths = [state];
  systemd.tmpfiles.rules = [
    "d ${state} 0700 dbalatero media -"
    "d ${state}/work 0700 dbalatero media -"
  ];
  systemd.services.ebook-import-directories = {
    description = "Create ebook inbox on the verified NAS export";
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
      test "$(findmnt -n -t nfs4 -T /mnt/warez -o SOURCE)" = 'truenas.vm.netcat.cloud:/mnt/warez/data'
      mkdir -p ${root}/incoming ${root}/.staging
      test "$(stat -c %d ${root}/incoming)" = "$(stat -c %d ${root}/.staging)"
    '';
  };
  systemd.services.ebook-import = {
    description = "Hand completed book torrents to the ebook inbox";
    requires = ["ebook-import-directories.service"];
    after = ["ebook-import-directories.service" "qbittorrent.service"];
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    serviceConfig = {
      Type = "oneshot";
      User = "dbalatero";
      Group = "media";
      UMask = "0007";
      ExecStart = "${importer}/bin/ebook-import work";
      TimeoutStartSec = "45min";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      NoNewPrivileges = true;
      ReadOnlyPaths = ["/mnt/warez/torrents"];
      ReadWritePaths = [state "${root}/incoming" "${root}/.staging"];
      MemoryMax = "1G";
      TasksMax = 32;
      StandardOutput = "journal";
      StandardError = "journal";
    };
  };
  systemd.timers.ebook-import = {
    wantedBy = ["timers.target"];
    timerConfig = {OnBootSec = "30s"; OnUnitInactiveSec = "30s"; AccuracySec = "5s";};
  };
  # Logs go only to common/nfs's size-bounded journal (512 MiB persistent,
  # 128 MiB runtime, 14 days). Successful job reports expire after 14 days;
  # unresolved review decisions and deduplication IDs are durable state.
  # Scratch extraction trees and incomplete copies are cleared on worker startup.
  # Neither retention mechanism touches torrent data or published inbox files.
}
