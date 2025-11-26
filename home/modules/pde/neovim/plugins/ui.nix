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
    plugins = {
      # better inputs and selects
      dressing.enable = true;

      colorizer.enable = true;

      which-key = {
        enable = true;
        settings = {
          spec = [
            (keyGroup "<leader>b" "+comment-box")
            (keyGroup "<leader>l" "+lsp")
            (keyGroup "<leader>m" "+marks")
            (keyGroup "<leader>n" "+a[n]notations")
            (keyGroup "<leader>s" "+search")
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
              rev = "master";
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
