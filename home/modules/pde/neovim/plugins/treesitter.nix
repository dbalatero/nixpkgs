{
  programs.nixvim = {
    plugins = {
      rainbow-delimiters.enable = true;

      treesitter = {
        enable = true;

        settings = {
          highlight.enable = true;
          indent = {
            enable = true;
            disable = ["python"];
          };

          incremental_selection = {
            enable = true;
            keymaps = {
              init_selection = "<c-space>";
              node_incremental = "<c-space>";
              scope_incremental = "<c-s>";
              node_decremental = "<M-space>";
            };
          };
        };
      };

      ts-autotag.enable = true;
      treesitter-context = {
        enable = true;
        settings = {
          max_lines = 2;
        };
      };

      vim-matchup = {
        enable = true;
        treesitter = {
          enable = true;
        };
      };

      treesitter-textobjects = {
        enable = true;

        settings = {
          move = {
            enable = true;
            set_jumps = true;

            goto_next_start = {
              "]m" = "@function.outer";
              "]]" = "@class.outer";
            };

            goto_next_end = {
              "]M" = "@function.outer";
              "][" = "@class.outer";
            };

            goto_previous_start = {
              "[m" = "@function.outer";
              "[[" = "@class.outer";
            };

            goto_previous_end = {
              "[M" = "@function.outer";
              "[]" = "@class.outer";
            };
          };

          select = {
            enable = true;
            lookahead = true;
            keymaps = {
              # You can use the capture groups defined in textobjects.scm
              "aa" = "@parameter.outer";
              "ia" = "@parameter.inner";
              "af" = "@function.outer";
              "if" = "@function.inner";
              "ac" = "@class.outer";
              "ic" = "@class.inner";
            };
          };

          swap = {
            enable = true;
            swap_next = {
              "<leader>a" = "@parameter.inner";
            };
            swap_previous = {
              "<leader>A" = "@parameter.inner";
            };
          };
        };
      };
    };
  };
}
