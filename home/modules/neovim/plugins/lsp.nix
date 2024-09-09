{
  config,
  lib,
  pkgs,
  ...
}: let
  helpers = config.lib.nixvim;
in {
  home.packages = [pkgs.alejandra];

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
    ];

    plugins = {
      lsp-format.enable = true;
      web-devicons.enable = true;

      fidget = {
        enable = true;

        progress = {
          ignore = [
            "none-ls"
            "null-ls"
          ];
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

          lua-ls = {
            enable = true;
            settings = {
              telemetry.enable = false;
              workspace.checkThirdParty = false;
            };
          };

          nil-ls = {
            enable = true;
            settings = {
              formatting.command = [(lib.getExe pkgs.alejandra) "--quiet"];
            };
          };

          tsserver.enable = true;
          yamlls = {
            enable = true;
            settings = {
              yaml = {
                schemas = {
                  # Github actions
                  "https://json.schemastore.org/github-workflow" = ".github/workflows/*.{yml,yaml}";
                  "https://json.schemastore.org/github-action" = ".github/action.{yml,yaml}";
                };
              };
            };
          };
        };
      };

      typescript-tools = {
        enable = true;

        onAttach =
          # lua
          ''
            function(client, bufnr)
              client.server_capabilities.documentFormattingProvider = false
              client.server_capabilities.documentRangeFormattingProvider = false
            end
          '';

        settings = {
          tsserverFilePreferences = {
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

      none-ls = {
        enable = true;

        sources = {
          diagnostics = {
            deadnix.enable = true;
          };

          formatting = {
            alejandra.enable = true; # nix
            prettierd.enable = true;
            rubyfmt.enable = true;
            shfmt.enable = true;
            stylua.enable = true;
          };
        };
      };
    };
  };
}
