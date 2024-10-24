{pkgs, ...}: let
  vim_test_stripe = pkgs.vimUtils.buildVimPlugin {
    name = "vim-test-stripe";
    src = builtins.fetchGit {
      url = "git@git.corp.stripe.com:dbalatero/vim-test-stripe.git";
      rev = "968f8c1124c5f2f6056379fc19dfba89155f45c4";
    };
  };
in {
  programs.nixvim = {
    extraPlugins = [vim_test_stripe];

    extraConfigLuaPost =
      # lua
      ''
        -- TODO: convert -> Lua someday or like never who cares
        vim.cmd([[
          let test#custom_runners = { 'ruby': ['payserver'], 'javascript': ['payserver'] }

          if fnamemodify(getcwd(), ':p') =~ "pay-server"
            let test#enabled_runners = ["ruby#payserver", "javascript#payserver"]
          end
        ]])
      '';
  };
}
