# Caddy HTTPS for the lab

Production was deployed and verified on 2026-09-30. Credentials are already
provisioned. The setup steps below are for fresh provisioning or deliberate
issuance testing; normal operation does not require rerunning them.

`hosts/caddy/caddy.nix` generates reverse proxies from the `services` list in
`lab/network.json`. Frontend names, backend machine references, schemes, and
ports come through `lab/network.nix`; one machine can host multiple services.
Special behavior stays in Nix, keyed by stable service `name`. Caddy uses Pi-hole
for backend resolution and public resolvers for DNS-01 propagation checks.
The gateway and Proxmox transports skip upstream certificate verification. Authentication
is deferred, including the existing passwordless Pi-hole dashboard.

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
