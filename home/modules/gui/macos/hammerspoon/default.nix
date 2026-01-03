{
  config,
  pkgs,
  ...
}: {
  home.packages = with pkgs; [
    blueutil
    m1ddc

    (writeShellScriptBin "daily" (builtins.readFile ./bin/daily.sh))
    (writeShellScriptBin "dnd-toggle" (builtins.readFile ./bin/dnd-toggle.sh))
  ];

  # Writable symlink to hammerspoon config - allows direct editing without Nix rebuilds
  home.file.".hammerspoon" = {
    source = config.lib.file.mkOutOfStoreSymlink
      "${config.home.homeDirectory}/.config/nixpkgs/home/modules/gui/macos/hammerspoon/config";
    force = true; # Replace existing hammerspoon directory
  };

  # Spoons must be vendored in config/Spoons/ or installed via Hammerspoon
  # To vendor SpoonInstall, download it to config/Spoons/SpoonInstall.spoon/
}
