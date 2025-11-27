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

      # Enhanced navigation with jump labels
      flash = {
        enable = true;
        settings = {
          labels = "asdfghjklqwertyuiopzxcvbnm";
          search = {
            multi_window = true;
            forward = true;
            wrap = true;
          };
          label = {
            uppercase = false;
            rainbow = {
              enabled = false;
            };
          };
          modes = {
            char = {
              enabled = false;
            };
          };
        };
      };

      # "gc" to comment visual regions/lines (treesitter-aware)
      ts-comments.enable = true;

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

      # Extended text objects (arguments, quotes, brackets, etc.)
      mini = {
        enable = true;
        modules = {
          ai = {
            n_lines = 500;
            custom_textobjects = helpers.mkRaw ''
              (function()
                local ai = require("mini.ai")

                -- Wrapper to make treesitter specs fail silently when parser unavailable
                local function ts_spec(...)
                  local spec = ai.gen_spec.treesitter(...)
                  return function(...)
                    local ok, result = pcall(spec, ...)
                    if ok then
                      return result
                    end
                    -- Return empty when treesitter fails (no parser available)
                    return { from = { line = 0, col = 0 }, to = { line = 0, col = 0 } }
                  end
                end

                return {
                  o = ts_spec({
                    a = { "@block.outer", "@conditional.outer", "@loop.outer" },
                    i = { "@block.inner", "@conditional.inner", "@loop.inner" },
                  }),
                  f = ts_spec({
                    a = "@function.outer",
                    i = "@function.inner",
                  }),
                  c = ts_spec({
                    a = "@class.outer",
                    i = "@class.inner",
                  }),
                  t = { "<([%p%w]-)%f[^<%w][^<>]->.-</%1>", "^<.->().*()</[^/]->$" },
                }
              end)()
            '';
          };
        };
      };

      neogen = {
        enable = true;
        settings = {
          snippet_engine = "luasnip";
        };
      };

      repeat.enable = true;

      sleuth.enable = true;
      vim-surround.enable = true;

      # Highlight and navigate TODO comments
      todo-comments = {
        enable = true;
        settings = {};
      };

      # Strip whitespace on save
      trim.enable = true;
    };

    extraPlugins = with pkgs; (
      with vimPlugins; [
        switch-vim # switch values with `gs`
        splitjoin-vim # fallback for treesj when no treesitter
        treesj # main splitjoin plugin
        vim-abolish # snake_case -> camelCase, etc
        vim-eunuch # Unix file operations (:Delete, :Move, :Rename, etc)
        vim-projectionist # :AV :AS for swapping between test & implementation
        quicker-nvim # better quickfix window
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

        -- Configure quicker.nvim for better quickfix
        require("quicker").setup({
          keys = {
            {
              ">",
              function()
                require("quicker").expand({
                  before = 2,
                  after = 2,
                  add_to_existing = true,
                })
              end,
              desc = "Expand quickfix context",
            },
            {
              "<",
              function()
                require("quicker").collapse()
              end,
              desc = "Collapse quickfix context",
            },
          },
        })

        -- Quickfix toggle keybinding
        vim.keymap.set("n", "<leader>q", function()
          require("quicker").toggle()
        end, { desc = "Toggle quickfix" })
      '';

    keymaps = [
      # flash
      {
        mode = ["n" "x" "o"];
        key = "s";
        action =
          # lua
          helpers.mkRaw ''
            function()
              require('flash').jump()
            end
          '';
        options = {
          desc = "Flash";
        };
      }

      # todo-comments
      {
        key = "]t";
        action =
          # lua
          helpers.mkRaw ''
            function()
              require('todo-comments').jump_next()
            end
          '';
        options = {
          desc = "Next todo comment";
        };
      }
      {
        key = "[t";
        action =
          # lua
          helpers.mkRaw ''
            function()
              require('todo-comments').jump_prev()
            end
          '';
        options = {
          desc = "Previous todo comment";
        };
      }
      {
        key = "<leader>st";
        action = "<cmd>TodoFzfLua<cr>";
        options = {
          desc = "Todo";
        };
      }
      {
        key = "<leader>sT";
        action = "<cmd>TodoFzfLua keywords=TODO,FIX,FIXME<cr>";
        options = {
          desc = "Todo/Fix/Fixme";
        };
      }

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
