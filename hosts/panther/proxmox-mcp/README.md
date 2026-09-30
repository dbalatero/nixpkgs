# Proxmox MCP on Panther

Panther runs the unmodified upstream [gilby125/mcp-proxmox](https://github.com/gilby125/mcp-proxmox/tree/6186c715b5ff393adc9fdf597a791c35bc2f90c7) server over local stdio. It connects to `192.168.1.250:8006` with TLS verification enabled and upstream's built-in read-only mode. There is no listening MCP network service.

Only `hosts/panther/configuration.nix` imports this module. Nix manages `/etc/codex/config.toml`, which Codex merges with the existing shared `~/.codex/config.toml` symlink. Other hosts do not get the package or MCP entry. See [Codex configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic#configuration-precedence).

## Create the API token

In the Proxmox UI:

1. Under **Datacenter → Permissions → Users**, add user `codex` in realm **Proxmox VE authentication server** (`pve`). This integration needs no interactive login password.
2. Under **Datacenter → Permissions**, add a user permission for `codex@pve`, path `/`, role **PVEAuditor**, with propagation enabled.
3. Under **API Tokens**, create token `panther` for that user. Leave **Privilege Separation** enabled. Save the secret when shown.
4. Add a token permission for `codex@pve!panther`, path `/`, role **PVEAuditor**, with propagation enabled.

Both the user and separated token need permissions. `PVEAuditor` supplies read-only access; do not grant an administrator role. These ACLs enforce inspection-only access independently of the MCP server. See [Proxmox permissions and API tokens](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc).

On Panther, create a private directory and token file:

```bash
install -d -m 700 ~/.config/proxmox-mcp
(umask 077; touch ~/.config/proxmox-mcp/token)
chmod 600 ~/.config/proxmox-mcp/token
```

Open `~/.config/proxmox-mcp/token` in your editor and paste **only the token secret**, not the full `user!token=secret` header. Keep it out of the repository and chat. The launcher reads this file at startup; replacing it does not require a Nix rebuild. The username and token ID are declared in `default.nix`.

## Trust the Proxmox certificate

For Proxmox's default certificates, copy `/etc/pve/pve-root-ca.pem` from the Proxmox host through an authenticated connection or its console, and save it on Panther as `~/.config/proxmox-mcp/ca.pem`. This is the public CA certificate, not a private key. Verify its source before trusting it.

The launcher supplies that file through `NODE_EXTRA_CA_CERTS` when present. If Proxmox already presents a certificate trusted by Node, no additional CA file is needed. The configured API address must match the certificate's subject alternative names. If the certificate covers only a DNS name, change `PROXMOX_HOST` in `default.nix` to that verified name and rebuild; do not disable TLS verification.

## Activate and verify

Apply the NixOS configuration with `./bin/switch` on Panther, then start a new Codex session. The MCP is optional (`required = false`), so missing credentials do not prevent Codex from starting. Use `codex mcp list` or `/mcp` to inspect registration, then ask it to list nodes, VMs, and storage pools.

The upstream server advertises write tools even in read-only mode, but refuses their execution. Some inspection tools, including detailed node status and guest-agent IP discovery, also require its elevated flag. Keep that flag false; ordinary node, VM, and storage listings work without it. Do not enable writes just to unlock those extra inspection tools.

## Audit and maintenance

Reviewed revision: `6186c715b5ff393adc9fdf597a791c35bc2f90c7`. The review covered credential loading, outbound requests, command execution, mutation guards, read/discovery paths, package scripts, dependencies, and upstream tests. This is a focused source review, not a guarantee about every dependency or Proxmox behavior.

- No telemetry or unrelated outbound destination was found in the server entry point; requests target the configured Proxmox API. Guest command execution is an elevated operation.
- Upstream disables TLS verification by default. This module explicitly enables it.
- Upstream's implicit `.env` loader reads the parent of its installation directory. The package installs an empty, immutable file there, so the launcher supplies configuration.
- Node/VM allowlists are not a consistent boundary for discovery. This setup relies on Proxmox ACLs, not those allowlists.
- Upstream uses SDK 0.4.0. The dependency audit reports [GHSA-w48q-cv73-mx4w](https://github.com/advisories/GHSA-w48q-cv73-mx4w), concerning DNS rebinding protection for HTTP servers. This deployment uses stdio and exposes no HTTP MCP listener. The SDK is intentionally unchanged rather than introducing a local migration.
- Source and dependencies are pinned. Installation scripts are disabled. The package runs upstream tests; API requests are mocked in those tests. Live authentication, CA trust, and effective ACLs require the user's token and must be verified separately.

No custom hardening patch or fork is applied. Updating the source revision requires reviewing changes, refreshing `package-lock.json` and `npmDepsHash`, and rerunning the tests. Do not switch to an unpinned runtime `npx` download.

## Verification on Panther

The Nix package built successfully and all 61 upstream tests passed. A local stdio smoke check initialized MCP, discovered 67 upstream tools, verified TLS verification was enabled, and confirmed a clone request was refused in read-only mode without contacting Proxmox. `./bin/switch` completed successfully, and `codex mcp get proxmox --json` confirmed the installed system registration. The shared user configuration still resolves to its original repository symlink.

Live Proxmox authentication and certificate verification remain pending the API token and CA provisioning above.
