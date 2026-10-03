{config, inputs, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  cfg = config.services.authentik;
  components = cfg.authentikComponents;
  authURL = "https://${network.servicesByName.authentik.fqdn}";
  blueprint = pkgs.writeText "netcat-authentik.yaml" ''
    version: 1
    metadata:
      name: netcat - Pi-hole
    entries:
      - model: authentik_blueprints.metaapplyblueprint
        attrs:
          identifiers:
            name: Default - Authentication flow
          required: true
      - model: authentik_blueprints.metaapplyblueprint
        attrs:
          identifiers:
            name: Default - Provider authorization flow (implicit consent)
          required: true
      - model: authentik_blueprints.metaapplyblueprint
        attrs:
          identifiers:
            name: Default - Provider invalidation flow
          required: true
      - model: authentik_core.group
        # Seed access once; subsequent memberships are managed in Authentik.
        state: created
        id: admins
        identifiers:
          name: Pi-hole admins
        attrs:
          users:
            - !Find [authentik_core.user, [username, akadmin]]
      - model: authentik_providers_proxy.proxyprovider
        id: pihole-provider
        identifiers:
          name: Pi-hole
        attrs:
          mode: forward_single
          external_host: https://${network.servicesByName.pihole-dns.fqdn}
          authentication_flow: !Find [authentik_flows.flow, [slug, default-authentication-flow]]
          authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
          invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]
      - model: authentik_core.application
        id: pihole-app
        identifiers:
          slug: pihole
        attrs:
          name: Pi-hole
          provider: !KeyOf pihole-provider
          meta_launch_url: https://${network.servicesByName.pihole-dns.fqdn}/admin/
          policy_engine_mode: any
      - model: authentik_policies.policybinding
        identifiers:
          target: !KeyOf pihole-app
          group: !KeyOf admins
          order: 0
      - model: authentik_policies.policybinding
        identifiers:
          target: !KeyOf pihole-app
          group: !Find [authentik_core.group, [name, authentik Admins]]
          order: 1
      - model: authentik_outposts.outpost
        identifiers:
          managed: goauthentik.io/outposts/embedded
        attrs:
          name: authentik Embedded Outpost
          type: proxy
          providers:
            - !KeyOf pihole-provider
          config:
            authentik_host: ${authURL}
            log_level: info
  '';
  # Authentik rejects blueprint symlinks that resolve outside blueprints_dir.
  blueprints = pkgs.runCommand "netcat-authentik-blueprints" {} ''
    mkdir -p $out/custom
    cp -rL ${components.staticWorkdirDeps}/blueprints/{default,system} $out/
    cp ${blueprint} $out/custom/netcat.yaml
  '';
  # Generate credentials on the host, never during Nix evaluation or a build.
  generateSecrets = pkgs.writeText "authentik-secrets.py" ''
    import base64
    import hashlib
    import os
    from pathlib import Path
    import secrets

    os.umask(0o077)
    state = Path("/var/lib/authentik-secrets")
    env = state / "environment"
    if not env.exists():
      password_file = state / "initial-admin-password"
      if not password_file.exists():
        password_file.write_text(secrets.token_urlsafe(32) + "\n")
      password = password_file.read_text().strip()
      salt = secrets.token_hex(16)
      digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 1000000)
      password_hash = "pbkdf2_sha256$1000000$" + salt + "$" + base64.b64encode(digest).decode()
      temporary = state / "environment.new"
      temporary.write_text(
        "AUTHENTIK_SECRET_KEY=" + secrets.token_urlsafe(64) + "\n"
        + "AUTHENTIK_BOOTSTRAP_PASSWORD_HASH='" + password_hash + "'\n"
      )
      temporary.replace(env)
  '';
  retention = pkgs.writeText "authentik-log-retention.py" ''
    from datetime import timedelta
    from django.utils.timezone import now
    from authentik.events.models import Event
    from authentik.tasks.models import TaskLog, TaskState
    from authentik.tenants.models import Tenant

    for tenant in Tenant.objects.filter(ready=True):
      tenant.event_retention = "days=30"
      tenant.save(update_fields=["event_retention"])
      with tenant:
        # Only audit logs; never users, sessions, cached data, or queued jobs.
        events = Event.objects.filter(created__lt=now() - timedelta(days=30))
        count, _ = events.delete()
        print(f"Removed {count} expired audit records")

    # Keep active/retrying jobs intact; delete only log rows of finished jobs.
    logs = TaskLog.objects.filter(
      timestamp__lt=now() - timedelta(days=14),
      task__state__in=[TaskState.DONE, TaskState.REJECTED],
    )
    count, _ = logs.delete()
    print(f"Removed {count} old completed-task log records")
  '';
in {
  imports = [inputs.authentik-nix.nixosModules.default];

  # Upstream authentik-nix publishes its builds to this signed cache.
  nix.settings = {
    extra-substituters = ["https://nix-community.cachix.org"];
    extra-trusted-public-keys = ["nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="];
  };

  services.authentik = {
    enable = true;
    environmentFile = "/var/lib/authentik-secrets/environment";
    settings = {
      blueprints_dir = blueprints;
      log_level = "info";
      disable_startup_analytics = true;
      error_reporting.enabled = false;
      listen = {
        http = ["127.0.0.1:${toString network.servicesByName.authentik.port}"];
        https = ["127.0.0.1:9443"];
        metrics = ["127.0.0.1:9300"];
        trusted_proxy_cidrs = ["127.0.0.1/32" "::1/128"];
      };
    };
    worker.listenHTTP = "127.0.0.1:9001";
    worker.listenMetrics = "127.0.0.1:9301";
  };

  systemd.services.authentik-secrets = {
    description = "Generate persistent Authentik bootstrap credentials";
    before = ["authentik-migrate.service" "authentik-worker.service" "authentik.service"];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      StateDirectory = "authentik-secrets";
      StateDirectoryMode = "0700";
      UMask = "0077";
      ExecStart = "${pkgs.python3}/bin/python3 ${generateSecrets}";
    };
  };
  systemd.services.authentik-migrate = {
    requires = ["authentik-secrets.service"];
    after = ["authentik-secrets.service"];
  };

  # Runtime output from Authentik, PostgreSQL and cleanup goes to the journal.
  # The existing host policy bounds it to 512 MiB persistent / 128 MiB runtime
  # and 14 days. Caddy access files rotate at 10 MiB with 5 archives / 14 days.
  services.postgresql.settings = {
    logging_collector = false;
    log_destination = "stderr";
  };
  systemd.services.authentik-log-retention = {
    description = "Apply 30-day Authentik audit retention and remove old audit logs";
    requires = ["authentik-migrate.service"];
    after = ["authentik-migrate.service" "authentik-worker.service"];
    serviceConfig = {
      Type = "oneshot";
      DynamicUser = true;
      User = "authentik";
      StateDirectory = "authentik";
      WorkingDirectory = "/var/lib/authentik";
      EnvironmentFile = cfg.environmentFile;
      ExecStart = "${components.manage}/bin/manage.py shell -c ${lib.escapeShellArg "exec(open('${retention}').read())"}";
    };
  };
  systemd.timers.authentik-log-retention = {
    wantedBy = ["timers.target"];
    timerConfig = {
      OnBootSec = "10m";
      OnCalendar = "daily";
      Persistent = true;
      RandomizedDelaySec = "15m";
    };
  };
}
