# Caddy HTTPS for the lab

Production was deployed and verified on 2026-09-30. Credentials are already
provisioned. The setup steps below are for fresh provisioning or deliberate
issuance testing; normal operation does not require rerunning them.

`hosts/caddy/caddy.nix` generates reverse proxies from the `services` list in
`lab/network.json`. Frontend names, backend machine references, schemes, and
ports come through `lab/network.nix`; one machine can host multiple services.
Special behavior stays in Nix, keyed by stable service `name`. Caddy uses Pi-hole
for backend resolution and public resolvers for DNS-01 propagation checks.
The gateway transport skips upstream certificate verification. Proxmox uses the
public cluster CA in `hosts/caddy/proxmox-ca.pem` and verifies its IP identity.
Pi-hole now has a declared Authentik gate at Caddy; see the Authentik section below.

## Authentik and Pi-hole

`hosts/caddy/authentik.nix` runs Authentik server, worker, embedded proxy outpost,
and local PostgreSQL on Caddy. The `authentik-nix` flake input pins its package
and NixOS module; the upstream signed nix-community cache supplies binaries.
`auth.netcat.cloud` resolves to Caddy through the shared inventory. Authentik's
HTTP and metrics listeners bind to loopback; Caddy provides HTTPS.

The Nix-generated blueprint declares the Pi-hole provider, application, and
`Pi-hole admins` group, initially containing `akadmin`. Group creation is
bootstrap-only so subsequent memberships can be managed in Authentik. Either
`authentik Admins` or `Pi-hole admins` grants access (the application combines
these bindings with OR). Pi-hole's dashboard and API
at `pihole.netcat.cloud` require an Authentik browser session. The outpost's
callback paths remain accessible for login. Requests are authenticated before
the existing `/admin/` rewrite. If Authentik is unavailable, access fails closed.

Pi-hole itself remains passwordless and its firewall is unchanged, as requested.
Direct IP access still bypasses this gate. Homepage's server-side Pi-hole widget
uses the private backend URL instead of the protected browser hostname.

On first boot, `authentik-secrets.service` generates the signing secret and a
random initial admin password locally. No secrets enter Git or the Nix store.
Log in at `https://auth.netcat.cloud` as `akadmin`; retrieve the initial password
in your own terminal on Caddy:

```bash
sudo cat /var/lib/authentik-secrets/initial-admin-password
```

Change the password after first login. The bootstrap hash is only used for initial
setup; restarts do not reset a changed password. Back up the PostgreSQL database
and `/var/lib/authentik-secrets` together with Authentik's media state. The
root-only initial-password file is a bootstrap credential, not a recovery key
after the password changes.

For a personal administrator account, open Admin interface → Directory → Users,
create the user and set its password. Add it to `authentik Admins` for full
administration, including Pi-hole access. Use `Pi-hole admins` for users who
only need Pi-hole access. These memberships survive
blueprint reconciliation. Browser SSO uses an Authentik session on
`auth.netcat.cloud` and a separate Pi-hole proxy cookie; no parent-domain cookie
is needed for later service integrations to reuse the Authentik session.

Runtime logs from Authentik, PostgreSQL, and cleanup use the existing journal
policy: 512 MiB persistent, 128 MiB runtime, maximum 14 days. Caddy's access logs
rotate at 10 MiB per file with five compressed archives and 14-day retention.
`authentik-log-retention.timer` runs daily and after boot: audit events retain
30 days, and completed/rejected-task log rows retain 14 days. These database
limits are age-based, not strict disk quotas; PostgreSQL reuses freed space.
Active job logs and application data are excluded from this cleanup.

Validate the deployed setup with:

```bash
systemctl is-active authentik authentik-worker postgresql caddy
systemctl list-timers authentik-log-retention.timer
curl -I https://pihole.netcat.cloud/admin/
curl -I https://pihole.netcat.cloud/api/info/version
```

Both Pi-hole requests should redirect to authentication without a browser
session. After login, verify the dashboard, API-backed statistics, and Homepage
widget. Apply future Caddy changes with `./bin/switch` on Caddy. DNS inventory
changes require a separate Pi-hole rebuild; this deployment does not rebuild it.

## Media dashboard authentication

The shared proxy blueprint also declares Radarr (`movies.netcat.cloud`), Lidarr
(`music.netcat.cloud`), Prowlarr (`trackers.netcat.cloud`), and Sonarr
(`tv.netcat.cloud`). Membership in either `Media admins` or `authentik Admins`
grants access to all four dashboards. `Media admins` is seeded with `akadmin`
once; later membership changes belong in Authentik. These apps expose full
administrative dashboards, so this group is for administrators, not requesters.
The embedded outpost's provider list is owned by the same blueprint as Pi-hole,
so reconciliation retains all five providers together.

Caddy gates every path, including APIs and live updates, except the outpost's
own login/callback paths. The apps use `AUTH__METHOD=External` and
`AUTH__REQUIRED=Enabled` through NixOS service settings. Backend ports remain
firewalled to Caddy; local callers retain their existing API keys. Do not replace
internal localhost URLs with the browser hostnames or add public API bypasses.
Prowlarr connects to Sonarr/Radarr/Lidarr over localhost; their indexer URLs point
back to localhost Prowlarr. Seerr likewise uses localhost Sonarr/Radarr URLs.
Seerr keeps Plex login and has no additional Authentik gate.

Apply the updated checkout on **Caddy first** with `./bin/switch`. Confirm the
blueprint is applied, all four applications appear in Authentik, and logged-out
requests to each dashboard and `/api/v1/system/status` (Lidarr/Prowlarr) or
`/api/v3/system/status` (Radarr/Sonarr) redirect to login. Then apply the updated
checkout on **media** with `./bin/switch` to remove the apps' second login.
Never enable external authentication before the proxy gate is in place.

After both switches:

- Check browser access with an allowed account, and denial for an account in
  neither allowed group. Confirm dashboards and live updates work.
- On media, run `sudo systemctl restart prowlarr-apps` to reconcile and test
  Prowlarr's three application connections; check its journal for successful tests.
- In each app, test its Prowlarr indexer connection; in Seerr, test both configured
  Sonarr and Radarr servers. These use the existing stored API keys.
- Verify a separate LAN client cannot connect directly to media ports 7878,
  8686, 8989, or 9696.

Existing retention covers these changes: each app keeps ten 1 MiB log archives
per level plus its active file, with the log database disabled. Caddy keeps five
compressed 10 MiB access-log archives per hostname for at most 14 days, with
cleanup during rotation. Both hosts' journals are bounded to 512 MiB persistent,
128 MiB runtime, and 14 days. Authentik's daily retention timer keeps 30 days of
audit events and 14 days of finished-task logs; these database limits are
age-based, not disk quotas. No additional log destinations are introduced.

Validation before deployment: both system derivations evaluated; the generated
blueprint parsed and Caddy configuration adapted. Disposable instances of all
four pinned apps accepted valid API keys, rejected invalid keys, and served the
UI with external authentication. Prowlarr's application tests passed against
all three disposable apps, and Seerr's API client read Sonarr/Radarr profiles
and roots. Generated Caddy routes were exercised with mock auth/backend servers:
unauthenticated browser/API requests redirected, authenticated requests passed,
spoofed identity headers did not bypass authentication, callbacks worked, and an
unavailable auth server failed closed. Live deployment and browser acceptance
checks remain separate from these isolated tests.

## Inventory refactor verification (2026-10-01)

Only the existing gateway, NAS, Proxmox, and Pi-hole services were migrated.
Generated Caddy virtual hosts and Pi-hole DNS host records match their captured
pre-refactor output byte for byte. All 22 inventory tests and 29 bootstrap tests
passed; both full system derivations evaluated. Home Manager emitted its existing
global-pkgs/overlay warnings. The refactor has not been deployed; apply the updated
checkout with `./bin/switch` on Pi-hole and Caddy when ready.

The following retention details describe the inventory refactor before the Homepage deployment below. Caddy access files remain under
`/var/log/caddy`, using its built-in file rotation defaults: 100 MiB per file,
10 compressed archives, and 90-day archive retention checked during rotation.
Caddy itself rotates/reopens these files; no separate cleanup timer is needed.
These limits apply per hostname, not as a total logging quota. See
[Caddy file logging](https://caddyserver.com/docs/caddyfile/directives/log#file).
Runtime logs use the systemd journal. Both evaluated hosts have no extra journald
overrides and retain systemd's default size limits (10% of each applicable
filesystem, capped at 4 GiB); journal housekeeping is internal to journald.
See [journald retention](https://www.freedesktop.org/software/systemd/man/252/journald.conf.html).
Pi-hole retains its declared daily/size-triggered logrotate policy and 30-day
query database history in `hosts/pihole-dns/pihole.nix`. No per-job logs are added.

## Provision Porkbun credentials locally

In Porkbun, create an API key under **Account → API Access**, save its secret
in your password manager, and enable **API Access** in the **Details** for
`netcat.cloud`. See [Porkbun's instructions](https://kb.porkbun.com/article/190-getting-started-with-the-porkbun-api).
Do not create public service A/AAAA records or WAN port forwards.

Run this in your own terminal on Caddy. The prompts hide input; the command
contains no credentials, and only root writes the resulting file. Do not run
it through an agent tool, terminal recording, or shell tracing.

```bash
sudo install -d -m 0755 -o root -g root /etc/caddy
sudo bash <<'SH'
set -eu
set +x
umask 077
read -r -s -p 'Porkbun API key: ' api_key </dev/tty
printf '\n' >/dev/tty
read -r -s -p 'Porkbun secret key: ' secret_key </dev/tty
printf '\n' >/dev/tty
[[ "$api_key" =~ ^[A-Za-z0-9_]+$ && "$secret_key" =~ ^[A-Za-z0-9_]+$ ]] || exit 1
install -m 0600 -o root -g root /dev/null /etc/caddy/porkbun.env
printf 'PORKBUN_API_KEY=%s\nPORKBUN_API_SECRET_KEY=%s\n' "$api_key" "$secret_key" > /etc/caddy/porkbun.env
unset api_key secret_key
SH
```

The service reads this root-owned `0600` file through systemd's
`EnvironmentFile`. Nix contains only its absolute path and runtime placeholders;
never use `builtins.readFile`, a Nix path literal, or `environment.etc.*.text`
for these credentials. Restart Caddy after rotating the file.

## Stage issuance, then deploy production

First set `lab.caddy.staging = true;` in `hosts/caddy/configuration.nix`.
After provisioning credentials, run from the canonical checkout on Caddy:

```bash
bin/switch --max-jobs 1 --cores 1
sudo systemctl status caddy --no-pager
sudo journalctl -u caddy --since '10 minutes ago' --no-pager
```

Confirm successful staging issuance for all four names before proceeding.
Staging certificates intentionally fail normal browser trust. Set
`lab.caddy.staging = false;` (or remove the override) and rerun `bin/switch`.
Staging and production certificate/account storage are separate directories
under `/var/lib/caddy`; switching modes restarts Caddy. Caddy automatically
renews production certificates using the same DNS credentials.

```bash
for name in gateway nas proxmox pihole; do
  curl --fail --show-error --silent --output /dev/null --dump-header - "https://$name.netcat.cloud/"
  curl --show-error --silent --output /dev/null --dump-header - "http://$name.netcat.cloud/"
done
curl --fail --show-error --silent --output /dev/null --dump-header - https://pihole.netcat.cloud/admin/
curl --fail --show-error --silent https://pihole.netcat.cloud/api/info/version
```

Production checks must work **without `-k`**. HTTP should redirect to HTTPS;
Pi-hole `/` should redirect to `/admin/`. NixOS serves Pi-hole at `/`, so Caddy
strips the `/admin` prefix while also passing its root-relative assets and API
paths through unchanged. TrueNAS redirects to its own HTTP frontend are
rewritten to HTTPS. Caddy preserves frontend Host headers, paths, cookies, and
its standard WebSocket upgrade behavior.

From a LAN browser, verify trusted HTTPS, gateway and TrueNAS logins,
navigation staying on the frontend names, Pi-hole dashboard/API behavior,
and WebSocket connections in developer tools. Check public DNS independently:

```bash
for name in gateway nas proxmox pihole; do
  dig @1.1.1.1 "$name.netcat.cloud" A +noall +answer
  dig @1.1.1.1 "$name.netcat.cloud" AAAA +noall +answer
done
```

The intended final state has no public service address answers. On 2026-09-30,
public lookups instead found wildcard parking CNAMEs to `pixie.porkbun.com`,
which resolves to public parking addresses. These existing records were left
untouched; review/remove the wildcard parking record in Porkbun if unused,
then repeat the checks. It does not point to Caddy or prevent DNS-01 issuance.
DNS-01 temporarily creates public TXT
records, and production certificates publish these names in certificate
transparency logs. Deployment evidence and outstanding checks are in
[the handoff](../plans/netcat-cloud-dns-and-caddy.md).

## Homepage (2026-10-01)

`hosts/caddy/homepage.nix` enables the native NixOS Homepage service with only
its title set to "Hello World". Services, bookmarks, and widgets are empty.
The inventory service `homepage` uses `hostname: "@"` for `netcat.cloud`;
Pi-hole resolves it to `192.168.1.203`. Caddy proxies to Homepage on
`127.0.0.1:8082`, and Homepage accepts the `netcat.cloud` Host header.
Services hosted on the Caddy machine use loopback upstreams.

The existing Porkbun DNS-01 configuration obtains and renews the root-domain
Let's Encrypt certificate. Access remains internal; no WAN forwarding or public
address records are required. HTTP redirects to HTTPS.

Homepage logs only to stdout/systemd journal. Host-wide journal limits are now
512 MiB persistent, 128 MiB runtime, and 14 days of retention. Journald performs
its own cleanup. Caddy access logs rotate at 10 MiB per file with five compressed
archives and 14-day archive retention checked during rotation. These are
per-hostname limits, not a combined quota; Caddy handles rotation and reopening.
Neither service adds per-job logs or requires a separate cleanup timer.

After applying with `./bin/switch`, verify with:

```bash
curl --fail https://netcat.cloud/ -o /dev/null
curl -I http://netcat.cloud/
systemctl is-active homepage-dashboard caddy
```

## Homepage widgets (2026-10-01)

Homepage now has Proxmox, Pi-hole v6, and SPCX stock widgets. Pi-hole shows
queries, blocked queries, blocking percentage, and blocklist size through
`https://pihole.netcat.cloud`. Its current passwordless API needs no widget key. Credentials are provisioned
manually in `/etc/homepage-dashboard.env` (root:root, mode 0600) and consumed
through the NixOS service's `environmentFiles`. Keep values in a password
manager, never in Git or Nix expressions. Edit with `sudoedit`; after initial
configuration deployment, restart `homepage-dashboard` to load changed values.

Required variables: `HOMEPAGE_VAR_PROXMOX_TOKEN_ID`,
`HOMEPAGE_VAR_PROXMOX_TOKEN_SECRET`, and `HOMEPAGE_VAR_FINNHUB_API_KEY`.
The Proxmox account and privilege-separated token both receive propagated
`PVEAuditor` permissions at `/`. The widget connects through Caddy's HTTPS
frontend; Caddy verifies backend TLS using the supplied cluster CA and the
inventory IP as the certificate identity. The CA is public and safe to track.
The existing journal and access-log retention policies cover these widgets.

## Dashboard appearance

The page is titled `netcat homelab`, using a dark slate palette with cyan,
mint, and lavender accents. `hosts/caddy/homepage.css` supplies local monospace
font fallbacks, a centered responsive layout, metric panels, and keyboard focus
styles. Infrastructure uses two columns on wider screens, followed by Markets.
The header contains the lab name and date/time. No external font service is used.


## Media routes and ordered deployment (2026-10-02)

The shared service inventory now declares these internal HTTPS routes:

| Service name | Frontend | Media backend port |
| --- | --- | --- |
| sonarr | tv.netcat.cloud | 8989 |
| radarr | movies.netcat.cloud | 7878 |
| lidarr | music.netcat.cloud | 8686 |
| audiobookshelf | audiobooks.netcat.cloud | 8000 |

All four entries use `machine: "media"` and `scheme: "http"`. Pi-hole generates
A records pointing to Caddy (`192.168.1.203`); Caddy generates upstreams at
`media.vm.netcat.cloud` (`192.168.1.205`). No handwritten duplicate virtual hosts
are needed. The existing proxy supports WebSockets and forwarded headers; see
[Caddy reverse proxy documentation](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

Media binds the apps on wildcard addresses, retaining localhost API access.
Its NixOS firewall admits the four TCP ports only from Caddy's inventory IPv4
address on `ens18`. App authentication remains enabled. The service ports are
derived from the same inventory as the routes. Media's existing app log and
journal policies continue to apply. Generated Caddy access logs use the existing
10 MiB / five compressed archives / 14-day per-hostname policy; Caddy's journal
uses 512 MiB persistent / 128 MiB runtime / 14-day limits. Pi-hole retains its
10 MiB rotation check, seven compressed archives, and 30-day query history.

Local validation: all three NixOS system derivations evaluated and all 24
inventory tests passed. Media was rebuilt successfully; all four services are
active, their authenticated localhost API requests returned 200, and the live
IPv4 firewall admits only Caddy on the four backend ports (IPv6 admits none).
Caddy and Pi-hole have not been deployed by this session; their network and TLS
checks below remain pending.

Deploy in this order: Media (already applied), Pi-hole, then Caddy. Run the
remote steps locally on their respective machines. Pull the updated repository
with `git pull --ff-only` before rebuilding; preserve unrelated local changes.
The new DNS names may temporarily fail HTTPS until Caddy is deployed. This is
expected during the handoff and does not indicate a DNS failure.

1. **Media:** already rebuilt and verified as described above. The permitted
   LAN source still needs verification from Caddy, and the denied source from
   Pi-hole; localhost API requests do not test the LAN firewall.
2. **Pi-hole:** apply `./bin/switch --max-jobs 1 --cores 1`. Confirm each new
   hostname resolves through Pi-hole to `192.168.1.203`. Check existing DNS
   records and DNS service health. Direct connections from Pi-hole to Media's
   four backend ports must fail. HTTPS verification waits until step 3; do not
   broaden Media's firewall or change DNS to work around a pending Caddy route.
3. **Caddy:** before rebuilding, request each backend from this machine using
   its frontend Host header. Arr roots should redirect to login; Audiobookshelf
   should return its UI. Unauthenticated protected API requests must remain
   rejected. Apply `./bin/switch --max-jobs 1 --cores 1`, using the existing
   production Porkbun DNS-01 credentials. Verify the generated routes and log
   retention, successful certificate issuance, and existing services. Test all
   four new HTTPS frontends using normal DNS with certificate verification;
   do not use `-k`. Verify UI assets and the Audiobookshelf Socket.IO/WebSocket
   handshake if available without login. Never print credentials, API keys,
   or cookies. After Caddy passes, HTTPS can also be checked from Pi-hole or
   a LAN browser.

Do not duplicate inventory entries, recreate credentials, reset app accounts,
change public address DNS, or alter WAN forwarding. `curl --resolve` remains
useful for isolating DNS from proxy issues, but is not needed for normal checks
once Pi-hole serves the new records.

Examples for Caddy (repeat the frontend test for all four aliases):

```bash
curl --connect-timeout 5 -sS -o /dev/null -w '%{http_code}\n' \
  -H 'Host: tv.netcat.cloud' http://media.vm.netcat.cloud:8989/
curl --connect-timeout 5 -sS -o /dev/null -w '%{http_code}\n' \
  https://tv.netcat.cloud/
curl -sSI http://tv.netcat.cloud/
```

Examples for Pi-hole (repeat for all four aliases):

```bash
dig @192.168.1.202 tv.netcat.cloud A +short
# After Caddy is deployed:
curl --connect-timeout 5 -sS -o /dev/null -w '%{http_code}\n' https://tv.netcat.cloud/
# This direct backend request is expected to fail from Pi-hole:
curl --connect-timeout 3 --max-time 5 -sS -o /dev/null http://192.168.1.205:8989/
```

A 200 or login redirect is expected for UI routes; 502 is not success. Report
certificate failures separately from app responses. Authenticated UI navigation
and playback remain user checks. These instructions are a handoff, not a claim
that Caddy or Pi-hole has already been deployed.
