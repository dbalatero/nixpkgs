# Add darwin-rebuild to path
export PATH="/run/current-system/sw/bin:$PATH"

IS_DARWIN="false"
if uname -a | grep -q "Darwin"; then
  IS_DARWIN="true"
fi

IS_STRIPE_DEVBOX="false"
if [[ -v STRIPE_USER ]]; then
  IS_STRIPE_DEVBOX="true"
fi

function is_darwin() {
  [[ "$IS_DARWIN" == "true" ]]
}

function is_stripe_devbox() {
  [[ "$IS_STRIPE_DEVBOX" == "true" ]]
}

function command_exists() {
  local name="$1"
  command -v "$name" >/dev/null 2>&1
}
