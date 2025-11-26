{
  config,
  lib,
  pkgs,
  ...
}: let
  helpers = config.lib.nixvim;

  lsp-format-latest = pkgs.vimUtils.buildVimPlugin {
    name = "lsp-format.nvim";
    src = pkgs.fetchFromGitHub {
      owner = "lukas-reineke";
      repo = "lsp-format.nvim";
      rev = "47de35b54ec95bb049f52016632394b914d4d9e9";
      hash = "sha256-x9jCrtsPaGIw+hn9HZg24Iqf+2lpHqRnBJri0Jd+bdc=";
    };
  };
in {
  home.packages = with pkgs; [
    alejandra
    typescript
  ];

  programs.nixvim = {
    keymaps = [
      # Diagnostics
      {
        key = "<leader>e";
        action = helpers.mkRaw "vim.diagnostic.open_float";
        options = {
          desc = "Open floating diagnostic message";
        };
      }
      {
        key = "<leader>q";
        action = helpers.mkRaw "vim.diagnostic.setloclist";
        options = {
          desc = "Open diagnostics list";
        };
      }
      {
        key = "gk";
        action =
          helpers.mkRaw
          # lua
          ''
            function()
              vim.diagnostic.goto_prev({ severity = vim.diagnostic.severity.ERROR })
            end
          '';
        options = {
          desc = "Go to previous error message";
        };
      }
      {
        key = "g<";
        action = helpers.mkRaw "vim.diagnostic.goto_prev";
        options = {
          desc = "Go to previous diagnostic";
        };
      }
      {
        key = "gj";
        action =
          helpers.mkRaw
          # lua
          ''
            function()
              vim.diagnostic.goto_next({ severity = vim.diagnostic.severity.ERROR })
            end
          '';

        options = {
          desc = "Go to next error message";
        };
      }
      {
        key = "g>";
        action = helpers.mkRaw "vim.diagnostic.goto_next";
        options = {
          desc = "Go to next diagnostic";
        };
      }

      # Trouble
      {
        key = "<leader>xx";
        action = "<cmd>Trouble diagnostics toggle<CR>";
        options = {
          silent = true;
          remap = false;
          desc = "Diagnostics (Trouble)";
        };
      }
      {
        key = "<leader>xb";
        action = "<cmd>TroubleToggle diagnostics toggle filter.buf=0<CR>";
        options = {
          silent = true;
          remap = false;
          desc = "Buffer Diagnostics (Trouble)";
        };
      }
      {
        key = "<leader>xl";
        action = "<cmd>Trouble loclist toggle<CR>";
        options = {
          silent = true;
          remap = false;
          desc = "Location List (Trouble)";
        };
      }
      {
        key = "<leader>xq";
        action = "<cmd>Trouble qflist toggle<CR>";
        options = {
          silent = true;
          remap = false;
          desc = "Quickfix List (Trouble)";
        };
      }
      {
        key = "gR";
        action = "<cmd>TroubleToggle lsp toggle focus=false win.position=right<CR>";
        options = {
          silent = true;
          remap = false;
          desc = "LSP Definitions / references / ... (Trouble)";
        };
      }

      # LSP
      {
        key = "gd";
        action = helpers.mkRaw "vim.lsp.buf.definition";
        options = {
          desc = "LSP: [G]o to [d]efinition";
        };
      }
      {
        key = "gD";
        action = helpers.mkRaw "vim.lsp.buf.declaration";
        options = {
          desc = "LSP: [G]o to [d]eclaration";
        };
      }
      {
        key = "gI";
        action = helpers.mkRaw "vim.lsp.buf.implementation";
        options = {
          desc = "[G]o to [i]mplementation";
        };
      }
      {
        key = "K";
        action = helpers.mkRaw "vim.lsp.buf.hover";
        options = {
          desc = "LSP: Hover documentation";
        };
      }
      {
        mode = ["n" "v"];
        key = "<leader>lc";
        action = helpers.mkRaw "vim.lsp.buf.code_action";
        options = {
          desc = "LSP: [C]ode action";
        };
      }
      {
        key = "<leader>li";
        action = ":LspInfo<CR>";
        options = {
          desc = "LSP: [I]nfo";
        };
      }
      {
        key = "<leader>lr";
        action = helpers.mkRaw "vim.lsp.buf.rename";
        options = {
          desc = "LSP: [R]ename";
        };
      }
      {
        key = "<leader>lt";
        action = helpers.mkRaw "vim.lsp.buf.type_definition";
        options = {
          desc = "LSP: [T]ype definition";
        };
      }
      {
        key = "<leader>lx";
        action = ":LspRestart<CR>";
        options = {
          desc = "LSP: Restart LSP(s) in buffer";
        };
      }
    ];

    plugins = {
      lsp-format = {
        enable = true;
        package = lsp-format-latest;
      };

      web-devicons.enable = true;

      fidget = {
        enable = true;

        settings = {
          progress = {
            ignore = [
              "none-ls"
              "null-ls"
            ];
          };
        };
      };

      trouble = {
        enable = true;

        settings = {
          use_diagnostic_signs = true;
        };
      };

      lsp = {
        enable = true;

        servers = {
          bashls.enable = true;
          cssls.enable = true;
          html.enable = true;

          jsonls = {
            enable = true;
            settings = {
              json = {
                schemas = [
                  {
                    description = "TypeScript compiler configuration file";
                    fileMatch = ["tsconfig.json" "tsconfig.*.json"];
                    url = "http://json.schemastore.org/tsconfig";
                  }
                  {
                    description = "Babel configuration";
                    fileMatch = [".babelrc.json" ".babelrc" "babel.config.json"];
                    url = "http://json.schemastore.org/lerna";
                  }
                  {
                    description = "ESLint config";
                    fileMatch = [".eslintrc.json" ".eslintrc"];
                    url = "http://json.schemastore.org/eslintrc";
                  }
                  {
                    description = "Prettier config";
                    fileMatch = [".prettierrc" ".prettierrc.json" "prettier.config.json"];
                    url = "http://json.schemastore.org/prettierrc";
                  }
                  {
                    description = "Vercel Now config";
                    fileMatch = ["now.json"];
                    url = "http://json.schemastore.org/now";
                  }
                  {
                    description = "Stylelint config";
                    fileMatch = [".stylelintrc" ".stylelintrc.json" "stylelint.config.json"];
                    url = "http://json.schemastore.org/stylelintrc";
                  }
                ];
              };
            };
          };

          lua_ls = {
            enable = true;
            settings = {
              telemetry.enable = false;
              workspace.checkThirdParty = false;
            };
          };

          nil_ls = {
            enable = true;
            settings = {
              formatting.command = [(lib.getExe pkgs.alejandra) "--quiet"];
            };
          };

          yamlls = {
            enable = true;
            settings = {
              format.enable = false;
              schemas = {
                # Github actions
                "https://json.schemastore.org/github-workflow" = ".github/workflows/*.{yml,yaml}";
                "https://json.schemastore.org/github-action" = ".github/action.{yml,yaml}";
              };
            };
          };
        };
      };

      typescript-tools = {
        enable = true;

        settings = {
          # expose_as_code_action = "all";

          settings = {
            tsserver_file_preferences = {
              # Inlay Hints
              includeInlayParameterNameHints = "all";
              includeInlayParameterNameHintsWhenArgumentMatchesName = true;
              includeInlayFunctionParameterTypeHints = true;
              includeInlayVariableTypeHints = true;
              includeInlayVariableTypeHintsWhenTypeMatchesName = true;
              includeInlayPropertyDeclarationTypeHints = true;
              includeInlayFunctionLikeReturnTypeHints = true;
              includeInlayEnumMemberValueHints = true;
            };
          };
        };
      };

      none-ls = {
        enable = true;

        sources = {
          diagnostics = {
            deadnix.enable = true;
            rubocop = {
              enable = true;
            };
          };

          formatting = {
            alejandra.enable = true; # nix
            prettierd = {
              enable = true;
              settings = {
                disabled_filetypes = [
                  "markdown"
                  "yaml"
                ];
              };
            };
            shfmt.enable = true;
            stylua.enable = true;
          };
        };
      };
    };
  };
}
