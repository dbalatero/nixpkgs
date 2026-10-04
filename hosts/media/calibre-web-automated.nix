{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  port = network.servicesByName.calibre-web-automated.port;
  state = "/var/lib/calibre-web-automated";
  secrets = "/var/lib/calibre-web-automated-secrets";
  root = "/mnt/warez/media/ebooks";
  proxyRule = "-i ens18 -s ${network.proxy.ip}/32 -p tcp --dport ${toString port} -j nixos-fw-accept";
  # Run after upstream cwa-init, before the web listener and ingest watcher.
  # NAS files must be created as UID 1000; root is squashed by the export.
  libraryInit = pkgs.writeScript "cwa-library-init" ''
    #!/usr/bin/with-contenv bash
    set -euo pipefail
    s6-setuidgid abc python3 /app/calibre-web-automated/scripts/auto_library.py
    python3 /nix-cwa/configure.py
  '';
in {
  virtualisation.podman.enable = true;
  virtualisation.oci-containers = {
    backend = "podman";
    containers.calibre-web-automated = {
      # Official v4.0.8, pinned multi-platform manifest (2026-10-04).
      image = "docker.io/crocodilestick/calibre-web-automated@sha256:5e00373854247750cc3e4479b492ae09293ff5e06ed10177f226634d97888679";
      networks = ["host"];
      log-driver = "journald";
      environment = {
        PUID = "1000";
        PGID = toString config.users.groups.media.gid;
        UMASK = "0007";
        TZ = "America/New_York";
        NETWORK_SHARE_MODE = "true";
        CWA_WATCH_MODE = "poll";
        CWA_PORT_OVERRIDE = toString port;
        TRUSTED_PROXY_COUNT = "1";
        # Isolate Books from generic session cookies used by other lab apps.
        COOKIE_PREFIX = "books_";
        NETCAT_AUTH_URL = "https://${network.servicesByName.authentik.fqdn}";
        NETCAT_BOOKS_URL = "https://${network.servicesByName.calibre-web-automated.fqdn}";
      };
      volumes = [
        "${state}:/config"
        "${root}/incoming:/cwa-book-ingest"
        "${root}/library:/calibre-library"
        "${secrets}/initial-admin-password:/run/secrets/cwa-admin-password:ro"
        "${secrets}/oidc-client-secret:/run/secrets/cwa-oidc-secret:ro"
        "${./cwa-configure.py}:/nix-cwa/configure.py:ro"
        "${./cwa_oidc.py}:/nix-cwa/cwa_oidc.py:ro"
        "${libraryInit}:/etc/s6-overlay/s6-rc.d/cwa-auto-library/run:ro"
        # Suppress upstream's unbounded OAuth debug file (may contain tokens).
        "/dev/null:/tmp/oauth_debug.log"
      ];
      extraOptions = ["--memory=4g" "--pids-limit=512" "--group-add=${toString config.users.groups.media.gid}"];
    };
  };

  systemd.tmpfiles.rules = [
    "d ${state} 0700 dbalatero media -"
    "d ${secrets} 0700 root root -"
  ];
  systemd.services.cwa-directories = {
    requires = ["ebook-import-directories.service"];
    after = ["ebook-import-directories.service"];
    serviceConfig = {Type = "oneshot"; RemainAfterExit = true; User = "dbalatero"; Group = "media"; UMask = "0007";};
    script = ''
      mkdir -p ${root}/library
    '';
  };
  systemd.services.cwa-secrets = {
    serviceConfig = {Type = "oneshot"; RemainAfterExit = true; UMask = "0077";};
    script = ''
      ${pkgs.python3}/bin/python - <<'PY'
      from pathlib import Path
      import secrets
      for name in ('initial-admin-password', 'oidc-client-secret'):
        path = Path('${secrets}') / name
        if not path.exists():
          with path.open('x') as output:
            output.write(secrets.token_urlsafe(32) + '\n')
      PY
    '';
  };
  systemd.services.podman-calibre-web-automated = {
    requires = ["cwa-directories.service" "cwa-secrets.service"];
    after = ["cwa-directories.service" "cwa-secrets.service"];
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    serviceConfig.TimeoutStartSec = lib.mkForce "15min";
    # NFS squashes UID 0; the launcher and container init need media traversal.
    serviceConfig.SupplementaryGroups = ["media"];
  };
  # Host networking ensures these INPUT rules govern container traffic too.
  networking.firewall.extraCommands = "iptables -A nixos-fw ${proxyRule}";
  networking.firewall.extraStopCommands = "iptables -D nixos-fw ${proxyRule} 2>/dev/null || true";

  # Daemon/container logs use common/nfs's journal limits (512M/128M/14 days).
  # These upstream per-job FileHandlers have no reopen hook. copytruncate
  # retains the active file descriptor; a small race may lose log lines.
  services.logrotate.settings.cwa-jobs = {
    files = ["${state}/convert-library.log" "${state}/epub-fixer.log"];
    frequency = "hourly";
    maxsize = "10M";
    rotate = 3;
    compress = true;
    missingok = true;
    notifempty = true;
    copytruncate = true;
    su = "dbalatero media";
  };
  systemd.timers.logrotate.timerConfig.OnCalendar = lib.mkForce "hourly";
  systemd.services.cwa-log-retention = {
    description = "Expire completed CWA logs and event history";
    environment.TZ = "America/New_York";
    serviceConfig = {
      Type = "oneshot";
      User = "dbalatero";
      Group = "media";
      ExecStart = "${pkgs.python3}/bin/python ${./cwa-log-retention.py} ${state}";
      ProtectSystem = "strict";
      ProtectHome = true;
      ReadWritePaths = [state];
      PrivateTmp = true;
      NoNewPrivileges = true;
    };
  };
  systemd.timers.cwa-log-retention = {
    wantedBy = ["timers.target"];
    timerConfig = {OnCalendar = "daily"; Persistent = true;};
  };
}
