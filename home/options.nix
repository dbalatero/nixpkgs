{lib, ...}:
with lib; {
  options.local.isStripe = mkOption {
    type = types.bool;
    default = false;
  };
}
