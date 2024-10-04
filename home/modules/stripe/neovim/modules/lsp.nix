{pkgs, ...}: {
  programs.nixvim = {
    extraPlugins = (
      map pkgs.vimUtils.buildVimPlugin [
        {
          name = "nvim-lspconfig-stripe";
          src = builtins.fetchGit {
            url = "git@git.corp.stripe.com:nms/nvim-lspconfig-stripe.git";
            rev = "3998c90e8b4962c0b145d769fb5a937991a973c8";
          };
        }
      ]
    );

    extraConfigLuaPost =
      # lua
      ''
        require("lspconfig_stripe")
        require("lspconfig").payserver_sorbet.setup({})

        -- Format on save in pay-server Ruby files.
        vim.api.nvim_create_autocmd("LspAttach", {
          group = vim.api.nvim_create_augroup("lsp", { clear = true }),
          callback = function(args)
            client = vim.lsp.get_client_by_id(args.data.client_id)

            if client and client.name == "payserver_sorbet" then
              vim.api.nvim_create_autocmd("BufWritePre", {
                buffer = args.buf,
                callback = function()
                  vim.lsp.buf.format({
                    async = false,
                    id = args.data.client_id,
                  })
                end,
              })
            end
          end
        })
      '';
  };
}
