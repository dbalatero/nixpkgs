{...}: {
  imports = [
    ../common.nix
  ];

  system.primaryUser = "db";

  homebrew.casks = [
    "chromium"
    "cursor"
    "linear-linear"
    "notion"
  ];
}
