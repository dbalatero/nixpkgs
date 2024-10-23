{
  programs.nixvim = {
    extraConfigLuaPost =
      # lua
      ''
        vim.g.github_enterprise_urls = { "https://git.corp.stripe.com" }
      '';
  };
}
