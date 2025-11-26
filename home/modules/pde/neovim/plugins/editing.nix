{
  config,
  pkgs,
  ...
}: let
  helpers = config.lib.nixvim;
in {
  programs.nixvim = {
    plugins = {
      auto-session.enable = true;

      # "gc" to comment visual regions/lines
      comment.enable = true;

      comment-box = {
        enable = true;
      };

      indent-blankline = {
        enable = true;
        settings = {
          indent = {
            char = "│";
          };

          exclude = {
            filetypes = [
              "alpha"
              "dashboard"
              "help"
              "lazy"
              "neo-tree"
              "Trouble"
            ];
          };
        };
      };

      marks.enable = true;

      neogen = {
        enable = true;
        settings = {
          snippet_engine = "luasnip";
        };
      };

      repeat.enable = true;

      sleuth.enable = true;
      vim-surround.enable = true;

      # Strip whitespace on save
      trim.enable = true;
    };

    extraPlugins = with pkgs; (
      with vimPlugins; [
        switch-vim # switch values with `gs`
        splitjoin-vim # fallback for treesj when no treesitter
        treesj # main splitjoin plugin
        vim-abolish # snake_case -> camelCase, etc
        vim-togglelist # <leader>q to toggle quickfix
        vim-projectionist # :AV :AS for swapping between test & implementation
      ]
    );

    globals = {
      # Disable the default keybindings so we can bind them manually.
      splitjoin_split_mapping = "";
      splitjoin_join_mapping = "";
    };

    extraConfigLuaPost =
      # lua
      ''
        require("treesj").setup({
          use_default_keymaps = false,
        })

        -- Configure a fallback to splitjoin.vim when a language is not supported.
        local langs = require("treesj.langs")["presets"]

        vim.api.nvim_create_autocmd({ "FileType" }, {
          pattern = "*",
          callback = function()
            if langs[vim.bo.filetype] then
              vim.keymap.set(
                "n",
                "gS",
                "<Cmd>TSJSplit<CR>",
                { buffer = true, desc = "[S]plit under cursor" }
              )
              vim.keymap.set(
                "n",
                "gJ",
                "<Cmd>TSJJoin<CR>",
                { buffer = true, desc = "[J]oin under cursor" }
              )
            else
              vim.keymap.set(
                "n",
                "gS",
                "<Cmd>SplitjoinSplit<CR>",
                { buffer = true, desc = "[S]plit under cursor" }
              )
              vim.keymap.set(
                "n",
                "gJ",
                "<Cmd>SplitjoinJoin<CR>",
                { buffer = true, desc = "[J]oin under cursor" }
              )
            end
          end,
        })
      '';

    keymaps = [
      # neogen
      {
        key = "<leader>nc";
        action =
          # lua
          helpers.mkRaw ''
            function()
              require('neogen').generate({ type = 'class' })
            end
          '';
        options = {
          silent = true;
          remap = false;
          desc = "Generate [c]lass annotations";
        };
      }
      {
        key = "<leader>nf";
        action =
          # lua
          helpers.mkRaw ''
            function()
              require('neogen').generate()
            end
          '';
        options = {
          silent = true;
          remap = false;
          desc = "Generate [f]unction annotations";
        };
      }

      # comment-box
      {
        mode = ["n" "v"];
        key = "<leader>bb";
        action =
          # lua
          helpers.mkRaw ''
            require('comment-box').llbox
          '';
        options = {
          remap = false;
          desc = "Left-aligned comment box";
        };
      }
      {
        mode = ["n" "v"];
        key = "<leader>bc";
        action =
          # lua
          helpers.mkRaw ''
            require('comment-box').lcbox
          '';
        options = {
          remap = false;
          desc = "Centered comment box";
        };
      }
      {
        mode = ["n" "v"];
        key = "<leader>br";
        action =
          # lua
          helpers.mkRaw ''
            require('comment-box').lrbox
          '';
        options = {
          remap = false;
          desc = "Right-aligned comment box";
        };
      }
      # marks.nvim
      {
        key = "<leader>m<space>";
        action = ":delm! | delm A-Z0-9<CR>";
        options = {
          silent = true;
          remap = false;
          desc = "Delete all marks";
        };
      }
    ];
  };
}
