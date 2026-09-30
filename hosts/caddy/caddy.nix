{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  cfg = config.lab.caddy;
  # Keys name inventory machines; aliases and backend DNS names come from there.
  upstreams = {
    gateway = {scheme = "https"; port = 443;};
    proxmox = {scheme = "https"; port = 8006;};
    truenas = {scheme = "http"; port = 80;};
    pihole-dns = {scheme = "http"; port = 80;};
  };
in {
  options.lab.caddy.staging = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = "Use Let's Encrypt staging and separate certificate storage for issuance testing.";
  };

  config = {
    assertions = lib.mapAttrsToList (name: _: {
      assertion = network.machinesByName.${name}.serviceFqdn != null;
      message = "Caddy upstream ${name} needs a public_hostname in lab/network.json";
    }) upstreams;

    services.caddy = {
      enable = true;
      package = pkgs.caddy.withPlugins {
        plugins = ["github.com/caddy-dns/porkbun@v0.3.1"];
        hash = "sha256-CjL8dMdnsiawaPiQGRvL3he4Ydd3nIbQs6tBWMwUbaw=";
      };
      environmentFile = "/etc/caddy/porkbun.env";
      # Restart when switching certificate stores between staging and production.
      enableReload = false;
      logFormat = "level INFO";
      globalConfig = ''
        admin 127.0.0.1:2019
        storage file_system {
          root /var/lib/caddy/${if cfg.staging then "staging" else "production"}
        }
      '';
      virtualHosts = lib.mapAttrs' (name: upstream: let
        machine = network.machinesByName.${name};
      in lib.nameValuePair machine.serviceFqdn {
        listenAddresses = [network.proxy.ip];
        extraConfig = ''
          tls {
            issuer acme {
              dir https://acme-${if cfg.staging then "staging-" else ""}v02.api.letsencrypt.org/directory
              disable_http_challenge
              disable_tlsalpn_challenge
              dns porkbun {
                api_key {env.PORKBUN_API_KEY}
                api_secret_key {env.PORKBUN_API_SECRET_KEY}
              }
              resolvers 1.1.1.1:53 8.8.8.8:53
            }
          }
          ${lib.optionalString (name == "pihole-dns") ''
            redir / /admin/ 302
            redir /admin /admin/ 308
            # NixOS pihole-web serves its dashboard at /; leave /api intact.
            uri /admin/* strip_prefix /admin
          ''}
          reverse_proxy ${upstream.scheme}://${machine.fqdn}:${toString upstream.port} {
            # Preserve the browser's hostname, including for HTTPS upstreams.
            header_up Host {host}
            ${lib.optionalString (builtins.elem name ["gateway" "proxmox"]) ''
              transport http {
                tls_insecure_skip_verify
              }
            ''}
            ${lib.optionalString (name == "truenas") ''
              header_down Location ^http://${lib.replaceStrings ["."] ["\\."] machine.serviceFqdn}(/.*)$ https://${machine.serviceFqdn}$1
            ''}
          }
        '';
      }) upstreams;
    };

    # Only the LAN-facing interface admits HTTP(S); admin stays on loopback.
    networking.firewall.interfaces.ens18 = {
      allowedTCPPorts = [80 443];
      allowedUDPPorts = [443];
    };

    # Caddy must traverse this directory to read its public generated config.
    # The credential file itself remains root-only (0600), read by systemd.
    systemd.tmpfiles.rules = ["d /etc/caddy 0755 root root -"];
  };
}
