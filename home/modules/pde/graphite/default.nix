{config, ...}: {
  xdg.configFile."graphite/aliases" = {
    source =
      config.lib.file.mkOutOfStoreSymlink
      "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/graphite/aliases.conf";
  };

  xdg.configFile."graphite/user_config" = {
    source =
      config.lib.file.mkOutOfStoreSymlink
      "${config.home.homeDirectory}/.config/nixpkgs/home/modules/pde/graphite/user_config.json";
  };
}
