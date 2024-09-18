# Add darwin-rebuild to path
export PATH="/run/current-system/sw/bin:$PATH"

IS_DARWIN="false"
if uname -a | grep -q "Darwin"; then
  IS_DARWIN="true"
fi

function is_darwin() {
  [[ "$IS_DARWIN" == "true" ]]
}

function command_exists() {
  local name="$1"
  command -v "$name" >/dev/null 2>&1
}
