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

    plugins = {
      lsp-format = {
        setup = {
          payserver_sorbet = {
            sync = true;
          };
        };
      };

      none-ls.settings = {
        debug = true;
      };

      none-ls.sources.diagnostics.rubocop = {
        settings = {
          command = "scripts/bin/rubocop-server/rubocop";
          extra_args = ["--except PrisonGuard/AutogenLoaderPreamble"];
        };
      };

      typescript-tools.settings = {
        # TODO: set this up once I get building working
        # This prevents spawning a second server, which can eat up way too
        # much memory in pay-server.
        # separate_diagnostic_server = false;

        # This prevents OOM crashes in pay-server.
        # tsserver_max_memory = 8192;
      };
    };

    extraConfigLuaPost =
      # lua
      ''
        require("lspconfig_stripe")
        require("lspconfig").payserver_sorbet.setup({
          -- Use the nixvim defined on_attach fn
          on_attach = _M.lspOnAttach,
        })

        local function target_contains_directory(target_path)
          return string.find(
            vim.fn.expand(vim.fn.getcwd()),
            vim.fn.expand(target_path),
            1,
            true
          ) ~= nil
        end

        if target_contains_directory("~/stripe/checkout") then
          require("null-ls").disable({"prettierd"})
        end

        -- -- Format on save in pay-server Ruby files.
        -- vim.api.nvim_create_autocmd("LspAttach", {
        --   group = vim.api.nvim_create_augroup("lsp", { clear = true }),
        --   callback = function(args)
        --     client = vim.lsp.get_client_by_id(args.data.client_id)
        --
        --     if client and client.name == "payserver_sorbet" then
        --       vim.api.nvim_create_autocmd("BufWritePre", {
        --         buffer = args.buf,
        --         callback = function()
        --           vim.lsp.buf.format({
        --             async = false,
        --             id = args.data.client_id,
        --           })
        --         end,
        --       })
        --     end
        --   end
        -- })
      '';
  };
}
