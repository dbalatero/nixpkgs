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
        treesitterIntegration = {
          enable = true;
        };
      };

      treesitter-textobjects = {
        enable = true;

        move = {
          enable = true;
          setJumps = true;

          gotoNextStart = {
            "]m" = "@function.outer";
            "]]" = "@class.outer";
          };

          gotoNextEnd = {
            "]M" = "@function.outer";
            "][" = "@class.outer";
          };

          gotoPreviousStart = {
            "[m" = "@function.outer";
            "[[" = "@class.outer";
          };

          gotoPreviousEnd = {
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
          swapNext = {
            "<leader>a" = "@parameter.inner";
          };
          swapPrevious = {
            "<leader>A" = "@parameter.inner";
          };
        };
      };
    };
  };
}
