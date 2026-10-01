# Handoff: Internal DNS and HTTPS for netcat.cloud

2026-10-01 inventory refactor: the current schema uses separate `machines` and `services` lists. Machine-level `public_hostname` and handwritten machine-keyed upstream tables have been replaced by service entries (`name`, `hostname`, `machine`, `scheme`, `port`). Gateway, NAS, Proxmox, and Pi-hole were migrated with identical generated DNS records and Caddy virtual hosts. No additional services were added or deployed. The sections below preserve the original deployment history; current schema instructions are in `lab/README.md` and `lab/caddy.md`.

## Status and transfer

As of 2026-09-30, Caddy at `192.168.1.203` is deployed with production Let's Encrypt certificates for all three services. Porkbun DNS-01 passed staging before production, using separate storage. DNS/Pi-hole and UniFi DHCP were already deployed. The user confirmed that browser access works. The requested Caddy work is complete; the user explicitly deferred public parking DNS cleanup. See the Caddy implementation evidence below for results.

The completed DNS changes are present in the Caddy checkout at `/home/dbalatero/.config/nixpkgs`. Bootstrap is complete: do not modify bootstrap, introduce reservations, or regenerate hardware configuration. The user authorized committing the Caddy implementation after deployment; publishing remains a user action.

The documentation commit is explicitly authorized with message `docs: add netcat.cloud DNS and Caddy handoff`. Implementation commits remain user-managed. Publishing/pushing this commit remains a user action.

Resume prompt:

> Read AGENTS.md and plans/netcat-cloud-dns-and-caddy.md, especially the Caddy implementation evidence. Caddy production HTTPS is deployed. The user confirmed browser access works and deferred public parking DNS cleanup. No implementation work remains; do not change public DNS unless newly requested. Preserve local changes and keep credentials out of chat, Git, and the Nix store.

## Inventory semantics and DNS

`lab/network.json` inventories known devices, including devices not managed by Nix. An entry does not authorize provisioning or configuring that device.

- Every machine entry generates `<hostname>.vm.netcat.cloud` pointing directly to its IP.
- Optional `public_hostname` generates `<public_hostname>.netcat.cloud` pointing to Caddy. Despite the field name, this creates only an internal DNS record.
- Caddy's upstream mappings remain explicitly configured in Nix.
- Rename the `.169` entry to `pihole-legacy`. Keep it until the user completes migration; do not schedule its removal or change the device itself.
- Generate DNS for the unmanaged iMessage Mac Mini without modifying that machine.
- Add top-level `domain: "netcat.cloud"`, `machine_subdomain: "vm"`, and `reverse_proxy_hostname: "caddy"`.
- Use the Caddy inventory entry created during bootstrap. Do not add reservations or modify bootstrap.

Initial service mappings:

| Inventory machine | Direct IP | `public_hostname` | Caddy upstream |
| --- | --- | --- | --- |
| `gateway` | `192.168.1.1` | `gateway` | `https://gateway.vm.netcat.cloud:443` |
| `pihole-legacy` | `192.168.1.169` | None | None |
| `truenas` | `192.168.1.201` | `nas` | `http://truenas.vm.netcat.cloud:80` |
| `pihole-dns` | `192.168.1.202` | `pihole` | `http://pihole-dns.vm.netcat.cloud:80` |
| `caddy` | `192.168.1.203` | None | None |
| `imessage` | `192.168.1.209` | None | None |
| `proxmox` | `192.168.1.250` | None | None |

Create a shared Nix inventory reader deriving names and addresses. Reject invalid DNS labels, duplicate aliases, and a missing proxy entry. Preserve inventory metadata and compatibility with existing bootstrap tooling.

Generate `services.pihole-ftl.settings.dns.hosts` using explicit records. Treat `netcat.cloud` as a local zone with negative answers for unknown names, rather than forwarding them upstream. Do not create wildcard DNS records. See [Pi-hole host records](https://docs.pi-hole.net/ftldns/configfile/#hosts).

Derive static addresses, gateway, and prefix for the NixOS Pi-hole and Caddy hosts from the inventory, preserving their actual interfaces. Keep Pi-hole's external upstream resolvers to avoid a self-resolution dependency. Caddy uses Pi-hole to resolve its internal upstream names.

## Caddy and TLS

- Import a Caddy service module into the existing bootstrapped host. Preserve hardware, boot, and home-manager configuration.
- Key handwritten upstream mappings by inventory machine name; derive frontend names from `public_hostname` so an alias change updates DNS and Caddy together.
- Redirect HTTP to HTTPS. Preserve paths, cookies, and WebSocket support. Redirect Pi-hole's frontend `/` to `/admin/` and proxy its dashboard/API.
- Serve browser-trusted certificates for `gateway.netcat.cloud`, `nas.netcat.cloud`, and `pihole.netcat.cloud`.
- Build Caddy with a pinned [Porkbun DNS plugin](https://github.com/caddy-dns/porkbun) using `pkgs.caddy.withPlugins`. The domain's public nameservers were verified to be Porkbun during planning.
- Automate issuance and renewal through DNS-01, using public resolvers for challenge propagation checks so the private DNS zone does not hide challenge records.
- Read `PORKBUN_API_KEY` and `PORKBUN_API_SECRET_KEY` through `services.caddy.environmentFile` from `/etc/caddy/porkbun.env`. The user provisions this root-owned, mode `0600` file. Credentials must not enter Git or the Nix store.
- Document enabling Porkbun API access for the domain. Do not request credentials in chat.
- Gateway backend policy: configure `tls_insecure_skip_verify` on its upstream transport. Do not introduce gateway certificate trust installation or maintenance. This is the user's chosen tradeoff: trusted TLS between browser and Caddy, encrypted but unverified TLS between Caddy and the gateway. Scope this setting to the gateway upstream. See [Caddy transport options](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#the-http-transport).
- Allow HTTP/HTTPS from the LAN; keep Caddy's admin API local. No public service A/AAAA records or WAN forwarding are needed.
- Shared authentication is deferred. Existing application logins and direct backend access remain unchanged. Pi-hole currently has a passwordless dashboard; adding a proxy does not add authentication.

## Bare hostnames and deployment

Completed by the user: UniFi DHCP distributes DNS server `192.168.1.202` and domain/search suffix `vm.netcat.cloud`; LAN hostname resolution is confirmed working. No further UniFi setup is pending for this phase. Clients retaining an older lease may still need to renew it. The suffix belongs in the shared `hosts/common/lab-network` module, imported by `hosts/common/nixos-vm`, and applies only to hosts listed in the inventory. Do not duplicate it in individual host files. DNS server selection remains host-specific. See [UniFi DHCP](https://help.ui.com/hc/en-us/articles/360012097513-UniFi-DHCP-Server).

`ssh truenas` then resolves the direct machine address; Caddy is not involved. This also works for other applications using the system resolver. Clients must use Pi-hole for these internal names; an unrelated secondary DNS server does not provide equivalent answers.

The implementing agent should:

1. Inspect the Caddy VM's hostname, address, inventory, flake entry, and Git status. Reconcile discrepancies without overwriting user changes. Confirm the user has completed bootstrap before proceeding with host integration.
2. Implement and evaluate both host configurations locally. Stage new files for flake visibility; leave implementation commits to the user. Use two-space indentation throughout.
3. Provide exact revision-transfer and deployment commands for Pi-hole. Do not assume this checkout's changes already exist on that VM. The Pi-hole host imports `hosts/pihole-dns/pihole.nix`; system service configuration belongs in NixOS modules.
4. After verifying the deployed Pi-hole DNS and provisioning credentials, apply Caddy locally with `bin/switch --max-jobs 1 --cores 1`. The user prefers `bin/switch` over direct rebuild commands. The repository permits applying NixOS configurations; preserve recovery access when changing networking.
5. Update lab documentation and this handoff with completed work, evidence, remaining actions, and resume commands. Correct stale DNS references and the claim that inventory entries do not establish DNS, without rewriting historical test fixtures merely because they use the old DNS address.

## Verification and boundaries

- Test record generation, unmanaged-device inclusion, the legacy rename, invalid/duplicate aliases, missing proxy entries, and inventory-tool compatibility.
- Evaluate both NixOS configurations; build and validate Caddy with its plugin. The pinned Nixpkgs inspected during planning supports `pkgs.caddy.withPlugins` and `services.caddy.environmentFile`; confirm against the checkout used for implementation.
- Verify direct/service DNS answers, negative answers, internet DNS, and bare hostnames after DHCP renewal.
- Test ACME staging before production issuance, keeping staging and production certificate state distinct.
- Verify warning-free browser HTTPS for all three services, redirects, dashboard logins, Pi-hole API behavior, and WebSockets.
- Specifically verify that gateway navigation and login remain on the frontend hostname without redirecting browsers to its untrusted backend address.
- Confirm service A/AAAA records remain absent from public DNS. Public certificates disclose service names through certificate transparency.
- Clearly distinguish local configuration checks from live deployment results. Missing credentials, a pending Pi-hole deployment, or an unavailable upstream must be recorded as outstanding rather than reported as passing.

## DNS-phase implementation evidence (historical)

- Handoff prepared on `pihole-dns` on 2026-09-30.
- At preparation time, no Caddy host configuration or Caddy inventory entry existed in this checkout.
- The user subsequently bootstrapped Caddy at `.203`; its host configuration and inventory entry are now present.
- DNS implementation on Pi-hole: `lab/network.nix` validates the inventory and exports `domain`, `machineDomain`, `machinesByName`, `proxy`, `prefixLength`, `gateway`, `dns`, and `dnsHosts`. Each enriched machine has `fqdn` and nullable `serviceFqdn`. Reuse this interface in the Caddy service module.
- Pi-hole generates machine and service records, with `netcat.cloud` treated as a private zone. The legacy entry is now `pihole-legacy`. Pi-hole and Caddy derive static network parameters from the inventory.
- Shared lab search configuration is in `hosts/common/lab-network`. Pi-hole uses per-link systemd-resolved routing for private lookups while retaining external DNS for public names. Search domains are attached to its private link, not its external global DNS servers.
- Shared VM configuration now declares zram swap at 50% of RAM, providing compressed swap capacity for rebuilds without allocating disk space.
- Automated checks: 14 Nix inventory/shared-search cases and 21 bootstrap tests pass. Both hosts' complete configurations, including shared networking and zram, built successfully. Pi-hole was switched successfully; Caddy was built only, not deployed.
- Live Pi-hole checks passed: all seven direct machine A records, all three service aliases pointing to `.203`, A/AAAA NXDOMAIN for an unknown private name and the retired `pihole.vm.netcat.cloud` name, public DNS resolution, and system resolution of bare `truenas` and `nas.netcat.cloud`. The legacy Pi remains in the inventory under `pihole-legacy`; only its old inventory DNS name was retired.
- Zram is active on Pi-hole: `/dev/zram0`, approximately 976 MiB capacity, priority 5. The full combined two-host build was killed on this 2 GiB VM before swap was enabled; individual builds were used instead.
- Pi-hole's live system is `/nix/store/siicr9935ba78ng5zkqh3xgps58xn11c-nixos-system-pihole-dns-26.11.20260803.104240a`.
- Caddy's validated system build is `/nix/store/r6c0ch0g1461r8p8gv293nanbdf01him-nixos-system-caddy-26.11.20260803.104240a` (before adding the proxy/TLS service).
- Caddy's shared network/zram configuration has not been applied remotely. Its proxy/TLS module, Porkbun credentials, certificate issuance, and browser tests are still outstanding. No public DNS changes were made.
- DNS/shared swap changes were committed and pushed to `origin/main` as `4dd36c1` (`Configure inventory-driven lab DNS and shared VM swap`).
- UniFi DHCP configuration is complete. After configuring DNS and the search domain, the user reported that LAN hostname resolution works. This is user-confirmed client evidence; the agent did not change the router or independently inspect those clients.
- At the end of the DNS phase, Caddy proxy/TLS implementation and deployment were still pending. The evidence below supersedes that remaining-work list.

## Caddy implementation evidence — 2026-09-30

- Worked locally on `caddy`; `ens18` has `192.168.1.203/24`. Initial Git status was clean. Hardware, bootstrap, existing DNS, networking, home-manager, and inventory were preserved. The only host integration change imports `hosts/caddy/caddy.nix`. The user subsequently authorized the implementation commit. No push was performed.
- The new service module uses `lab/network.nix` and machine-keyed mappings for `gateway`, `truenas`, and `pihole-dns`. Frontend aliases and backend FQDNs are derived from inventory. No duplicated service DNS inventory or backend IP literals were added.
- Built Caddy `2.11.4` with `github.com/caddy-dns/porkbun@v0.3.1` using `pkgs.caddy.withPlugins`; dependency hash is `sha256-CjL8dMdnsiawaPiQGRvL3he4Ydd3nIbQs6tBWMwUbaw=`. The build's plugin/version checks passed, and `caddy list-modules` contains `dns.providers.porkbun`. The generated Caddyfile successfully adapted to JSON; inspection confirmed DNS-01-only issuance, public propagation resolvers, runtime credential placeholders, all mappings, and gateway-only unverified backend TLS.
- Both complete NixOS configurations evaluated; all 14 inventory/search regression cases passed. The Caddy system built successfully. Evaluation still emits the pre-existing Home Manager `useGlobalPkgs`/overlay warning; it did not prevent the builds or switches.
- Verified Pi-hole resolves the service alias to `.203`, and the system resolver resolves the three backend names to `.1`, `.201`, and `.202`. Gateway HTTPS returned `200`; TrueNAS HTTP returned `302`; Pi-hole API returned `200`.
- Found NixOS `pihole-web` serves its dashboard at `/` (`paths.webhome = "/"`), so directly proxying `/admin/` initially returned `404`. Caddy now redirects frontend `/` to `/admin/`, strips the `/admin` prefix for dashboard requests, and preserves `/api` and root-relative asset paths. Pi-hole itself was not changed or redeployed.
- TrueNAS emitted `Location: http://nas.netcat.cloud/ui/` even with `X-Forwarded-Proto: https`. Its proxy rewrites redirects for that exact frontend authority to HTTPS. Gateway requests explicitly retain the frontend Host header; initial page retrieval stays on the frontend name. The user subsequently confirmed browser access works; this is user-reported validation, not an agent-observed authenticated session.
- The user provisioned `/etc/caddy/porkbun.env` locally. Only metadata was inspected: `root:root`, `0600`. No credential values were read into tools, chat, repository files, or Nix expressions. Provisioning instructions are in [lab/caddy.md](../lab/caddy.md), including enabling domain API access in Porkbun and hidden terminal prompts. Nix references only the absolute runtime file path, not its contents.
- The first staging start failed because `/etc/caddy` was `0700`, preventing the service user from traversing it to read the generated config. Added a declarative tmpfiles rule for directory mode `0755`; the environment file remains root-only `0600`. Retried successfully through `bin/switch --max-jobs 1 --cores 1`.
- Staging certificates issued successfully for all three names, with journal evidence identifying `acme-staging-v02.api.letsencrypt.org-directory`. Staging HTTPS returned gateway `200`, NAS `302` to its HTTPS `/ui/`, Pi-hole root `302` to `/admin/`, and dashboard `200`.
- Removed the temporary `lab.caddy.staging = true` override and applied production with `bin/switch --max-jobs 1 --cores 1`. All three production certificates issued successfully. State is isolated in `/var/lib/caddy/staging` and `/var/lib/caddy/production`; configuration changes restart Caddy. Automatic renewal remains managed by Caddy through Porkbun DNS-01.
- Active production system: `/nix/store/qrg8rg5bqjqihlcrn9dsdz0l1rjag25z-nixos-system-caddy-26.11.20260803.104240a`. Successful staging system: `/nix/store/zg2zfghlssqvpga2kvcfzspg8mn1g4vk-nixos-system-caddy-26.11.20260803.104240a`. A final rebuild restricted Pi-hole prefix stripping to `/admin/*`; all production probes passed again. Caddy is both active and enabled; directory and credential modes remain `0755` and `0600` respectively.
- Live listeners: TCP `192.168.1.203:80` and `:443`, UDP `192.168.1.203:443`, admin TCP `127.0.0.1:2019`. Firewall permits HTTP(S) only on `ens18`. No WAN forwarding was configured.
- Production TLS verification passed using Python's default system CA store and hostname verification, without `-k` or a custom trust anchor. Certificates have the correct individual DNS SANs, Let's Encrypt issuers `YE1`/`YE2`, and expire on 2026-12-29. The production probe exercised real services rather than mock upstreams:
  - HTTP `/` on all three names: `308` to the corresponding HTTPS URL.
  - Gateway HTTPS `/`: `200`.
  - NAS HTTPS `/`: `302` to `https://nas.netcat.cloud/ui/`; `/ui/`: `200`.
  - Pi-hole HTTPS `/`: `302` to `/admin/`; `/admin`: `308` to `/admin/`; `/admin/`, `/admin/queries`, and `/queries`: `200`.
  - Pi-hole JavaScript, stylesheet, and `/api/info/version`: `200`; API returned valid version JSON and the dashboard identifies `/api` as its API URL.
  - TrueNAS `/websocket`: `101 Switching Protocols` with a verified `Sec-WebSocket-Accept` response over trusted frontend TLS. No application login was needed for this handshake.
- Public DNS check did **not** meet the planned no-address-answer condition: all three service names return a parking CNAME to `pixie.porkbun.com`, which resolves to `207.207.210.107`/`207.207.210.229`. An arbitrary nonexistent name queried against authoritative `curitiba.ns.porkbun.com` also returns that CNAME, demonstrating existing wildcard parking. Public nameservers are Porkbun. No service records or parking records were created/removed by this work; only ACME challenge TXT records were managed automatically.
- After the final deployment, recent Caddy logs contained no errors. Public TXT lookups for all three `_acme-challenge` names returned only the existing wildcard parking CNAME and no challenge TXT records, consistent with successful cleanup.

## Completion and deferred work

1. Browser validation: the user reported, “I checked the browser and it works.” This completes user acceptance of the deployed setup. Individual authenticated flows were not independently observed by the agent.
2. Public wildcard parking DNS cleanup is explicitly deferred by the user and is not a completion blocker. The existing record remains unchanged. The original empty-public-answer condition is therefore not met, as documented above; revisit only if requested.
3. Publish the authorized implementation commit when ready. No Pi-hole deployment or transfer is required for these Caddy-only changes. Authentication remains deferred; the Pi-hole dashboard is still passwordless.

From the canonical Caddy checkout:

```bash
sudo systemctl is-active caddy
curl --fail --show-error --silent --output /dev/null --dump-header - https://gateway.netcat.cloud/
curl --fail --show-error --silent --output /dev/null --dump-header - https://nas.netcat.cloud/ui/
curl --fail --show-error --silent --output /dev/null --dump-header - https://pihole.netcat.cloud/admin/
curl --fail --show-error --silent https://pihole.netcat.cloud/api/info/version
```

For future configuration changes use `bin/switch --max-jobs 1 --cores 1`.
Production is already deployed; do not repeat staging or recreate credentials
merely to resume validation. Never print `/etc/caddy/porkbun.env` or service
environment contents. See [the deployment guide](../lab/caddy.md) for credential
rotation/provisioning and staging procedures when they are actually needed.
