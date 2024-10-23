{pkgs, ...}: {
  programs.nixvim = {
    extraPlugins = (
      map pkgs.vimUtils.buildVimPlugin [
        {
          name = "stripe-luasnips.nvim";
          src = builtins.fetchGit {
            url = "git@git.corp.stripe.com:dbalatero/stripe-luasnips.nvim.git";
            rev = "cf6f2e9d4d031c4526a2dfb82c83372416d66f93";
          };
        }
      ]
    );

    extraConfigLuaPost =
      # lua
      ''
        require("stripe-luasnips")

        local snipConfig = require('stripe-luasnips.config')
        snipConfig.payfile.opus_project = "ocs_api_platform"
        snipConfig.todo.jira_project = "RUN_OCS_API"
      '';
  };
}
