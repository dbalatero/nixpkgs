{...}: {
  programs.zsh.sessionVariables = {
    MISE_NODE_COREPACK = "true";
  };
  programs.mise = {
    enable = true;
    enableZshIntegration = true;
    globalConfig = {
      tools = {
        node = "lts";
      };
      settings = {
        idiomatic_version_file_enable_tools = ["node"];
        not_found_auto_install = true;
      };
    };
  };
}
