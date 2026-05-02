{ config, ... }: {
  # Symlink Half-Life userconfig.cfg to Steam directory
  home.file.".local/share/Steam/steamapps/common/Half-Life/valve/userconfig.cfg" = {
    source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/nixpkgs/home/modules/gui/gaming/half-life/userconfig.cfg";
  };
}
