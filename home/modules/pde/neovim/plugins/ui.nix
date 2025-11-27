{
  config,
  pkgs,
  ...
}: let
  keyGroup = key: group: {
    __unkeyed-1 = "${key}";
    group = "${group}";
  };
  helpers = config.lib.nixvim;
in {
  programs.nixvim = {
    # Catppuccin colorscheme
    colorschemes.catppuccin = {
      enable = true;
      settings = {
        flavor = "mocha";
      };
    };

    plugins = {
      # better inputs and selects
      dressing.enable = true;

      colorizer.enable = true;

      # Modern UI for messages, cmdline, and popups
      noice = {
        enable = true;
        settings = {
          lsp = {
            # override markdown rendering so that **cmp** and other plugins use **Treesitter**
            override = {
              "vim.lsp.util.convert_input_to_markdown_lines" = true;
              "vim.lsp.util.stylize_markdown" = true;
              "cmp.entry.get_documentation" = true;
            };
          };
          presets = {
            bottom_search = true; # use a classic bottom cmdline for search
            command_palette = true; # position the cmdline and popupmenu together
            long_message_to_split = true; # long messages will be sent to a split
            inc_rename = false; # enables an input dialog for inc-rename.nvim
            lsp_doc_border = false; # add a border to hover docs and signature help
          };
        };
      };

      # Dependencies for noice.nvim
      notify.enable = true;

      which-key = {
        enable = true;
        settings = {
          spec = [
            (keyGroup "<leader>b" "+comment-box")
            (keyGroup "<leader>l" "+lsp")
            (keyGroup "<leader>m" "+marks")
            (keyGroup "<leader>n" "+a[n]notations")
            (keyGroup "<leader>s" "+search")
            (keyGroup "<leader>sn" "+noice")
            (keyGroup "<leader>x" "+trouble")
          ];
        };
      };
    };

    extraConfigLuaPost =
      /*
      lua
      */
      ''
        -- Configure lualine
        require("lualine").setup({
          options = {
            icons_enabled = true,
            theme = "catppuccin",
          },
          sections = {
            lualine_a = { "mode" },
            lualine_b = {},
            lualine_c = { "filename", "diff", "diagnostics" },
            lualine_x = { "filesize", "encoding", "fileformat", "filetype" },
            lualine_y = {},
            lualine_z = { "LineNoIndicator" },
          },
        })

        vim.g.vimfiler_force_overwrite_statusline = 0
        vim.g.vimfiler_as_default_explorer = 1
        vim.g.vimshell_force_overwrite_statusline = 0

        vim.fn["vimfiler#custom#profile"]("default", "context", { safe = 0 })

        -- bind the minus key to show the file explorer in the dir of the current open
        -- buffer's file
        vim.keymap.set(
          { "n" },
          "-",
          ":VimFilerBufferDir<CR>",
          {
            noremap = true,
            silent = true,
            desc = "Navigate to current directory",
          }
        )

        -- Noice keybindings
        vim.keymap.set("n", "<leader>snl", function()
          require("noice").cmd("last")
        end, { desc = "Noice Last Message" })

        vim.keymap.set("n", "<leader>snh", function()
          require("noice").cmd("history")
        end, { desc = "Noice History" })

        vim.keymap.set("n", "<leader>sna", function()
          require("noice").cmd("all")
        end, { desc = "Noice All" })

        vim.keymap.set("n", "<leader>snd", function()
          require("noice").cmd("dismiss")
        end, { desc = "Dismiss All" })

        -- Scroll in LSP hover docs
        vim.keymap.set({ "i", "n", "s" }, "<c-f>", function()
          if not require("noice.lsp").scroll(4) then
            return "<c-f>"
          end
        end, { silent = true, expr = true, desc = "Scroll forward" })

        vim.keymap.set({ "i", "n", "s" }, "<c-b>", function()
          if not require("noice.lsp").scroll(-4) then
            return "<c-b>"
          end
        end, { silent = true, expr = true, desc = "Scroll backward" })
      '';

    extraPlugins = with pkgs;
      (
        with vimPlugins; [
          unite-vim
          vimfiler-vim
        ]
      )
      ++ (
        map vimUtils.buildVimPlugin [
          {
            # Use latest version from GitHub to avoid hash mismatch
            name = "lualine.nvim";
            src = fetchFromGitHub {
              owner = "nvim-lualine";
              repo = "lualine.nvim";
              rev = "47f91c416daef12db467145e16bed5bbfe00add8";
              hash = "sha256-OpLZH+sL5cj2rcP5/T+jDOnuxd1QWLHCt2RzloffZOA=";
            };
          }
          {
            # disable highlights automatically on cursor move
            name = "vim-cool";
            src = fetchFromGitHub {
              owner = "romainl";
              repo = "vim-cool";
              rev = "662e7b11064cbeedad17c45d2fe926e78d3cd0b6";
              hash = "sha256-M91iWqytUR6AldM2H4U/79nX2ba5gN4I/z7m0iltjcY=";
            };
          }
          {
            name = "vim-line-no-indicator";
            src = fetchFromGitHub {
              owner = "drzel";
              repo = "vim-line-no-indicator";
              rev = "004c731581621021674546e0f076e1c900f8163a";
              hash = "sha256-k7YTfws50pUmGV1ShJvx6HY3qBc43NO7OxVtuLiRwJs=";
            };
          }
        ]
      );
  };
}
