{...}: {
  imports = [
    ../common.nix
  ];

  system.primaryUser = "db";

  homebrew.casks = [
    "chromium"
    "linear-linear"
    "notion"
  ];
}
