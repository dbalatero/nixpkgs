# Handoff: Internal DNS and HTTPS for netcat.cloud

## Status and transfer

Planning is complete. No DNS, proxy, network, or credential configuration has been changed for this plan. This handoff was prepared on `pihole-dns`; implementation will take place in a later Codex session on the Caddy VM.

The user will independently bootstrap a NixOS VM named `caddy` at `192.168.1.203`, publish this document's commit, and bring it into that VM's checkout at `/home/dbalatero/.config/nixpkgs`. Do not modify bootstrap, introduce reservations, or regenerate hardware configuration.

The documentation commit is explicitly authorized with message `docs: add netcat.cloud DNS and Caddy handoff`. Implementation commits remain user-managed. Publishing/pushing this commit remains a user action.

Resume prompt:

> Read AGENTS.md and plans/netcat-cloud-dns-and-caddy.md. Implement this handoff from the Caddy VM. Preserve bootstrap-generated configuration and local changes. Record completed work, validation evidence, and outstanding deployment steps in the handoff.

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

Document user-applied UniFi DHCP settings: DNS server `192.168.1.202`, domain/search suffix `vm.netcat.cloud`, followed by client lease renewal. Configure the same suffix declaratively on the static Pi-hole and Caddy VMs. See [UniFi DHCP](https://help.ui.com/hc/en-us/articles/360012097513-UniFi-DHCP-Server).

`ssh truenas` then resolves the direct machine address; Caddy is not involved. This also works for other applications using the system resolver. Clients must use Pi-hole for these internal names; an unrelated secondary DNS server does not provide equivalent answers.

The implementing agent should:

1. Inspect the Caddy VM's hostname, address, inventory, flake entry, and Git status. Reconcile discrepancies without overwriting user changes. Confirm the user has completed bootstrap before proceeding with host integration.
2. Implement and evaluate both host configurations locally. Stage new files for flake visibility; leave implementation commits to the user. Use two-space indentation throughout.
3. Provide exact revision-transfer and deployment commands for Pi-hole. Do not assume this checkout's changes already exist on that VM. The Pi-hole host imports `hosts/pihole-dns/pihole.nix`; system service configuration belongs in NixOS modules.
4. After Pi-hole deployment and credential provisioning, apply Caddy locally. The repository permits applying NixOS configurations; preserve recovery access when changing networking.
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

## Implementation evidence

- Handoff prepared on `pihole-dns` on 2026-09-30.
- At preparation time, no Caddy host configuration or Caddy inventory entry existed in this checkout.
- No implementation or live service validation has been performed for this plan.
- Next action: the user publishes this handoff and independently bootstraps Caddy at `.203`, then resumes Codex on that VM with the prompt above.
