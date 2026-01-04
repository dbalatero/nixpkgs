{config, ...}: {
  # Symlink Half-Life userconfig.cfg to Steam directory
  home.file.".local/share/Steam/steamapps/common/Half-Life/valve/userconfig.cfg" = {
    source = ./userconfig.cfg;
  };
}
