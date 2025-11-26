{
  config,
  pkgs,
  ...
}: let
  helpers = config.lib.nixvim;
in {
  programs.nixvim = {
    extraPlugins = (
      map pkgs.vimUtils.buildVimPlugin [
        {
          name = "dir-telescope.nvim";
          src = pkgs.fetchFromGitHub {
            owner = "princejoogie";
            repo = "dir-telescope.nvim";
            rev = "805405b9f98dc3470f8676773dc0e6151a9158ed";
            hash = "sha256-B/cZUkjAVi52jopBwZJYmiaVf8PqnawusnSGOx7dDqs=";
          };
        }
      ]
    );

    extraConfigLuaPost = ''
      require("dir-telescope").setup({
        hidden = false,
        respect_gitignore = true,
      })

      require("telescope").load_extension("dir")
    '';

    keymaps = [
      {
        key = "<leader>sdf";
        action = helpers.mkRaw ''
          function (...)
            require("telescope").extensions.dir.find_files(...)
          end
        '';
        options = {
          desc = "[S]earch [d]irectory for [f]iles";
        };
      }
      {
        key = "<leader>sdg";
        action = helpers.mkRaw ''
          function (...)
            require("telescope").extensions.dir.live_grep({
              layout_strategy = "vertical",
            })(...)
          end
        '';
        options = {
          desc = "[S]earch [d]irectory by [g]rep";
        };
      }
    ];

    plugins = {
      telescope = {
        enable = true;

        extensions = {
          fzf-native = {
            enable = true;
            settings = {
              override_generic_sorter = true;
              override_file_sorter = true;
            };
          };
          ui-select.enable = true;
        };

        settings = {
          defaults = {
            mappings = {
              i = {
                "<C-u>" = false;
                "<C-d>" = false;
              };
            };

            vimgrep_arguments = [
              "rg"
              "--hidden"
              "--glob"
              "!{node_modules/*,.git/*,.aws/*,.yarn/*}"
              "--color=never"
              "--no-heading"
              "--with-filename"
              "--line-number"
              "--column"
              "--smart-case"
            ];
          };

          pickers = {
            buffers = {
              ignore_current_buffer = true;
              sort_mru = true;
            };

            find_files = {
              layout_strategy = "vertical";
              find_command = [
                "rg"
                "--files"
                "--hidden"
                "--glob"
                "!{node_modules/*,.git/*,.aws/*,.yarn/*}"
                "--color=never"
              ];
            };

            live_grep = {
              layout_strategy = "vertical";
            };
          };
        };

        keymaps = {
          "<leader>sb" = {
            action = "buffers";
            options.desc = "[S]earch existing [b]uffers";
          };

          "<leader><space>" = {
            action = "find_files";
            options.desc = "Find files";
          };

          "<leader>sf" = {
            action = "find_files";
            options.desc = "[S]earch [f]iles";
          };

          "<leader>sg" = {
            action = "live_grep";
            options.desc = "[S]earch by [g]rep";
          };

          "<leader>sh" = {
            action = "help_tags";
            options.desc = "[S]earch [h]elp tags";
          };

          "<leader>si" = {
            action = "diagnostics";
            options.desc = "[S]earch d[i]agnostics";
          };

          "<leader>sw" = {
            action = "grep_string";
            options.desc = "[S]earch current [w]ord";
          };
        };
      };
    };
  };
}
