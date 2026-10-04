{config, inputs, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  cfg = config.services.authentik;
  components = cfg.authentikComponents;
  authURL = "https://${network.servicesByName.authentik.fqdn}";
  mediaApps = ["radarr" "lidarr" "prowlarr" "sonarr"];
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
      - model: authentik_core.group
        # Seed once; later memberships are managed in Authentik.
        state: created
        id: media-admins
        identifiers:
          name: Media admins
        attrs:
          users:
            - !Find [authentik_core.user, [username, akadmin]]
      ${lib.replaceStrings ["\n"] ["\n  "] (lib.concatMapStringsSep "\n" (name: ''
      - model: authentik_providers_proxy.proxyprovider
        id: ${name}-provider
        identifiers:
          name: ${lib.toUpper (builtins.substring 0 1 name)}${builtins.substring 1 (-1) name}
        attrs:
          mode: forward_single
          external_host: https://${network.servicesByName.${name}.fqdn}
          authentication_flow: !Find [authentik_flows.flow, [slug, default-authentication-flow]]
          authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
          invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]
      - model: authentik_core.application
        id: ${name}-app
        identifiers:
          slug: ${name}
        attrs:
          name: ${lib.toUpper (builtins.substring 0 1 name)}${builtins.substring 1 (-1) name}
          provider: !KeyOf ${name}-provider
          meta_launch_url: https://${network.servicesByName.${name}.fqdn}
          policy_engine_mode: any
      - model: authentik_policies.policybinding
        identifiers:
          target: !KeyOf ${name}-app
          group: !KeyOf media-admins
          order: 0
      - model: authentik_policies.policybinding
        identifiers:
          target: !KeyOf ${name}-app
          group: !Find [authentik_core.group, [name, authentik Admins]]
          order: 1
      '') mediaApps)}
      - model: authentik_outposts.outpost
        identifiers:
          managed: goauthentik.io/outposts/embedded
        attrs:
          name: authentik Embedded Outpost
          type: proxy
          providers:
            - !KeyOf pihole-provider
            ${lib.concatMapStringsSep "\n        " (name: "- !KeyOf ${name}-provider") mediaApps}
          config:
            authentik_host: ${authURL}
            log_level: info
  '';
  booksBlueprint = pkgs.writeText "netcat-books-authentik.yaml" ''
    version: 1
    metadata:
      name: netcat - Books
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
      - model: authentik_blueprints.metaapplyblueprint
        attrs:
          identifiers:
            name: System - OAuth2 Provider - Scopes
          required: true
      - model: authentik_core.group
        # Seed once; invite additional readers by adding them to this group.
        state: created
        id: books-users
        identifiers:
          name: Books users
        attrs:
          users:
            - !Find [authentik_core.user, [username, akadmin]]
      - model: authentik_providers_oauth2.oauth2provider
        id: books-provider
        identifiers:
          name: Books
        attrs:
          client_type: confidential
          client_id: netcat-books
          # Authentik 2026.8 defaults new providers to no enabled grants.
          grant_types:
            - authorization_code
          client_secret: !Env NETCAT_BOOKS_OIDC_CLIENT_SECRET
          authentication_flow: !Find [authentik_flows.flow, [slug, default-authentication-flow]]
          authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
          invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]
          redirect_uris:
            - matching_mode: strict
              url: https://${network.servicesByName.calibre-web-automated.fqdn}/login/generic/authorized
          sub_mode: hashed_user_id
          issuer_mode: per_provider
          property_mappings:
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-openid]]
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-profile]]
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-email]]
      - model: authentik_core.application
        id: books-app
        identifiers:
          slug: books
        attrs:
          name: Books
          provider: !KeyOf books-provider
          meta_launch_url: https://${network.servicesByName.calibre-web-automated.fqdn}
          policy_engine_mode: any
      - model: authentik_policies.policybinding
        identifiers:
          target: !KeyOf books-app
          group: !KeyOf books-users
          order: 0
      - model: authentik_policies.policybinding
        identifiers:
          target: !KeyOf books-app
          group: !Find [authentik_core.group, [name, authentik Admins]]
          order: 1
  '';
  # Authentik rejects blueprint symlinks that resolve outside blueprints_dir.
  blueprints = pkgs.runCommand "netcat-authentik-blueprints" {} ''
    mkdir -p $out/custom
    cp -rL ${components.staticWorkdirDeps}/blueprints/{default,system} $out/
    cp ${blueprint} $out/custom/netcat.yaml
    cp ${booksBlueprint} $out/custom/books.yaml
  '';
  # Generate credentials on the host, never during Nix evaluation or a build.
  generateSecrets = pkgs.writeText "authentik-secrets.py" ''
    import base64
    import hashlib
    import os
    from pathlib import Path
    import re
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

    # Provision this shared secret from media's CWA secret file before enabling
    # Books. Missing credentials affect only the separate Books blueprint.
    books_secret_file = state / "books-oidc-client-secret"
    lines = [line for line in env.read_text().splitlines()
      if not line.startswith("NETCAT_BOOKS_OIDC_CLIENT_SECRET=")]
    if books_secret_file.exists():
      books_secret = books_secret_file.read_text().strip()
      if not re.fullmatch(r"[A-Za-z0-9_-]{32,255}", books_secret):
        raise ValueError("Invalid Books OIDC client secret: expected URL-safe random text")
      lines.append("NETCAT_BOOKS_OIDC_CLIENT_SECRET=" + books_secret)
    temporary = state / "environment.new"
    temporary.write_text("\n".join(lines) + "\n")
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
