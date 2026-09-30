{pkgs, ...}: let
  server = pkgs.callPackage ./package.nix {};
  launcher = pkgs.writeShellScriptBin "proxmox-mcp" ''
    tokenFile="$HOME/.config/proxmox-mcp/token"
    if [ ! -s "$tokenFile" ]; then
      echo "Create $tokenFile with your Proxmox API token secret (mode 0600)." >&2
      exit 1
    fi
    export PROXMOX_HOST=192.168.1.250
    export PROXMOX_PORT=8006
    export PROXMOX_USER=codex@pve
    export PROXMOX_TOKEN_NAME=panther
    export PROXMOX_ALLOW_ELEVATED=false
    export PROXMOX_VERIFY_TLS=true
    export PROXMOX_TOKEN_VALUE="$(cat "$tokenFile")"
    if [ -f "$HOME/.config/proxmox-mcp/ca.pem" ]; then
      export NODE_EXTRA_CA_CERTS="$HOME/.config/proxmox-mcp/ca.pem"
    fi
    exec ${pkgs.nodejs}/bin/node ${server}/lib/proxmox-mcp/index.js
  '';
in {
  environment.systemPackages = [launcher];

  # Codex merges this system layer with the existing shared user symlink.
  environment.etc."codex/config.toml".text = ''
    [mcp_servers.proxmox]
    command = "${launcher}/bin/proxmox-mcp"
    enabled = true
    required = false
    startup_timeout_sec = 10
    tool_timeout_sec = 60
    default_tools_approval_mode = "prompt"
  '';
}
