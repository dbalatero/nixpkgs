{pkgs, ...}: {
  services.journald.extraConfig = ''
    SystemMaxUse=1G
    SystemKeepFree=5G
    RuntimeMaxUse=128M
    MaxRetentionSec=30day
  '';

  # nginx's module supplies compression and USR1 to reopen rotated files.
  # maxsize is checked hourly, so this is not a hard disk quota.
  services.logrotate.settings.nginx = {
    frequency = "daily";
    rotate = 14;
    maxsize = "50M";
  };

  nix.settings = {
    keep-build-log = true;
    compress-build-log = true;
  };
  # Logs are independent of store outputs: no package GC is performed here.
  systemd.services.nix-build-log-cleanup = {
    description = "Expire inactive Nix build logs older than 30 days";
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.python3}/bin/python3 ${./prune-build-logs.py}";
      User = "root";
      Nice = 19;
      IOSchedulingClass = "idle";
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ReadWritePaths = ["/nix/var/log/nix/drvs"];
      ProtectHome = "read-only";
      PrivateTmp = true;
    };
  };
  systemd.timers.nix-build-log-cleanup = {
    wantedBy = ["timers.target"];
    timerConfig = {
      OnCalendar = "daily";
      RandomizedDelaySec = "1h";
      Persistent = true;
    };
  };
}
