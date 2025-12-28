IS_DARWIN="false"
if uname -a | grep -q "Darwin"; then
  IS_DARWIN="true"
fi

IS_NIXOS="false"
if uname -a | grep -qi nixos || [ -f /etc/NIXOS ]; then
  IS_NIXOS="true"
fi

# Add darwin-rebuild to path (only on macOS)
if [[ "$IS_DARWIN" == "true" ]]; then
  export PATH="/run/current-system/sw/bin:$PATH"
fi

function is_darwin() {
  [[ "$IS_DARWIN" == "true" ]]
}

function is_nixos() {
  [[ "$IS_NIXOS" == "true" ]]
}

function command_exists() {
  local name="$1"
  command -v "$name" >/dev/null 2>&1
}
