{
  lib,
  pkgs,
  ...
}: {
  home.packages = [pkgs.alejandra];

  programs.nixvim = {
    plugins = {
      lsp-format.enable = true;

      lsp = {
        enable = true;

        servers = {
          bashls.enable = true;
          cssls.enable = true;
          html.enable = true;
          lua-ls.enable = true;

          nil-ls = {
            enable = true;
            settings = {
              formatting.command = [(lib.getExe pkgs.alejandra) "--quiet"];
            };
          };

          tsserver.enable = true;
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
