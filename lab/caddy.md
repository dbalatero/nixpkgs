# Caddy HTTPS for the lab

Production was deployed and verified on 2026-09-30. Credentials are already
provisioned. The setup steps below are for fresh provisioning or deliberate
issuance testing; normal operation does not require rerunning them.

`hosts/caddy/caddy.nix` maps inventory machines to reverse proxies. Frontend
aliases and backend names come from `lab/network.nix`. Caddy uses Pi-hole for
backend resolution and public resolvers for DNS-01 propagation checks. Only
the gateway transport skips upstream certificate verification. Authentication
is deferred, including the existing passwordless Pi-hole dashboard.

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

Confirm successful staging issuance for all three names before proceeding.
Staging certificates intentionally fail normal browser trust. Set
`lab.caddy.staging = false;` (or remove the override) and rerun `bin/switch`.
Staging and production certificate/account storage are separate directories
under `/var/lib/caddy`; switching modes restarts Caddy. Caddy automatically
renews production certificates using the same DNS credentials.

```bash
for name in gateway nas pihole; do
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
for name in gateway nas pihole; do
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
