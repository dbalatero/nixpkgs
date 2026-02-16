{...}: {
  home.file.".default-gems".text = ''
    bundler
  '';
  programs.zsh.sessionVariables = {
    MISE_NODE_COREPACK = "true";
  };
  programs.mise = {
    enable = true;
    enableZshIntegration = true;
    globalConfig = {
      tools = {
        node = "lts";
        ruby = "latest";
      };
      settings = {
        idiomatic_version_file_enable_tools = ["node" "ruby"];
        not_found_auto_install = true;
      };
    };
  };
}
