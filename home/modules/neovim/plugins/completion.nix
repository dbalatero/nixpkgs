{
  config,
  pkgs,
  ...
}: let
  helpers = config.lib.nixvim;
in {
  programs.nixvim = {
    extraPlugins = with pkgs; (
      with vimPlugins; [
        cmp-under-comparator
        lspkind-nvim
      ]
    );

    # reference: https://github.com/oddlama/nix-config/blob/3383fd9a142fe012461b9dc9bfa7a4a40d348aec/users/myuser/neovim/completion.nix#L14
    plugins = {
      friendly-snippets.enable = true;

      luasnip = {
        enable = true;
        settings = {
          history = true;
          enable_autosnippets = true;
        };
      };

      cmp-buffer.enable = true;
      cmp_luasnip.enable = true;
      cmp-nvim-lsp.enable = true;

      cmp = {
        enable = true;
        settings = {
          sources = [
            {name = "nvim_lsp";}
            {name = "luasnip";}
            {
              name = "buffer";
              option.get_bufnrs =
                # lua
                helpers.mkRaw ''
                  function()
                    return vim.api.nvim_list_bufs()
                  end
                '';
            }
          ];

          formatting.format = helpers.mkRaw ''
            require("lspkind").cmp_format({
              mode = "symbol_text",
              max_width = 50,
            })
          '';

          mapping = {
            "<C-d>" =
              # lua
              "cmp.mapping.scroll_docs(-4)";

            "<C-Space>" =
              # lua
              "cmp.mapping.complete({})";

            "<C-f>" =
              # lua
              "cmp.mapping.scroll_docs(4)";

            "<CR>" =
              # lua
              ''
                cmp.mapping.confirm({
                  behavior = cmp.ConfirmBehavior.Replace,
                  select = true,
                })
              '';

            "<S-Tab>" =
              # lua
              ''
                cmp.mapping(function(fallback)
                  if cmp.visible() then
                    cmp.select_prev_item({
                      behavior = cmp.SelectBehavior.Insert
                    })
                  elseif luasnip.jumpable(-1) then
                    luasnip.jump(-1)
                  else
                    fallback()
                  end
                end, {"i", "s"})
              '';

            "<Tab>" =
              # lua
              ''
                cmp.mapping(function(fallback)
                  local luasnip = require("luasnip")
                  local has_words_before = function()
                    if vim.api.nvim_buf_get_option(0, "buftype") == "prompt" then
                      return false
                    end

                    local line, col = unpack(vim.api.nvim_win_get_cursor(0))

                    return col ~= 0
                      and vim.api.nvim_buf_get_text(0, line - 1, 0, line - 1, col, {})[1]:match("^%s*$") == nil
                  end

                  if cmp.visible() and has_words_before() then
                    cmp.select_next_item({
                      behavior = cmp.SelectBehavior.Insert
                    })
                  elseif luasnip.expandable() then
                    luasnip.expand()
                  elseif luasnip.expand_or_locally_jumpable() then
                    luasnip.expand_or_jump()
                  else
                    fallback()
                  end
                end, { 'i', 's' })
              '';
          };

          sorting = {
            priority_weight = 2;
            comparators = [
              # Sort by distance of the word from the cursor
              #   https://github.com/hrsh7th/cmp-buffer#locality-bonus-comparator-distance-based-sorting
              (helpers.mkRaw ''
                function(...)
                  return require("cmp_buffer"):compare_locality(...)
                end
              '')
              (helpers.mkRaw ''require("cmp.config.compare").offset'')
              (helpers.mkRaw ''require("cmp.config.compare").exact'')
              (helpers.mkRaw ''require("cmp.config.compare").score'')
              (helpers.mkRaw ''require("cmp-under-comparator").under'')
              (helpers.mkRaw ''require("cmp.config.compare").recently_used'')
              (helpers.mkRaw ''require("cmp.config.compare").locality'')
              (helpers.mkRaw ''require("cmp.config.compare").kind'')
              (helpers.mkRaw ''require("cmp.config.compare").sort_text'')
              (helpers.mkRaw ''require("cmp.config.compare").length'')
              (helpers.mkRaw ''require("cmp.config.compare").order'')
            ];
          };

          snippet.expand =
            # lua
            ''
              function(args)
                luasnip.lsp_expand(args.body)
              end
            '';
        };
      };
    };

    extraConfigLuaPost =
      /*
      lua
      */
      ''
        require("lspkind").init()

        local ls = require("luasnip")
        ls.add_snippets("all", {
          ls.snippet("todo", { ls.text_node("TODO(dbalatero): ") }),
        })
      '';
  };
}
