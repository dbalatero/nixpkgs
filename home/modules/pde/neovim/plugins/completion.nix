{
  config,
  pkgs,
  ...
}: let
  helpers = config.lib.nixvim;
in {
  programs.nixvim = {
    plugins = {
      friendly-snippets.enable = true;

      luasnip = {
        enable = true;
        settings = {
          history = true;
          enable_autosnippets = true;
        };
      };

      # blink.cmp - modern completion plugin
      blink-cmp = {
        enable = true;

        settings = {
          keymap = {
            preset = "default";

            "<C-space>" = ["show" "show_documentation" "hide_documentation"];
            "<C-e>" = ["hide"];
            "<CR>" = ["accept" "fallback"];
            "<Tab>" = ["select_next" "snippet_forward" "fallback"];
            "<S-Tab>" = ["select_prev" "snippet_backward" "fallback"];
            "<C-d>" = ["scroll_documentation_up" "fallback"];
            "<C-f>" = ["scroll_documentation_down" "fallback"];
          };

          appearance = {
            use_nvim_cmp_as_default = true;
            nerd_font_variant = "mono";
          };

          sources = {
            default = ["lsp" "path" "snippets" "buffer"];
          };

          completion = {
            accept = {
              auto_brackets = {
                enabled = true;
              };
            };

            menu = {
              draw = {
                columns = [
                  {__unkeyed-1 = "kind_icon";}
                  {
                    __unkeyed-1 = "label";
                    __unkeyed-2 = "label_description";
                    gap = 1;
                  }
                ];
              };
            };

            documentation = {
              auto_show = true;
              auto_show_delay_ms = 200;
            };
          };

          snippets = {
            expand =
              helpers.mkRaw
              # lua
              ''
                function(snippet)
                  require("luasnip").lsp_expand(snippet)
                end
              '';

            active =
              helpers.mkRaw
              # lua
              ''
                function(filter)
                  if filter and filter.direction then
                    return require("luasnip").jumpable(filter.direction)
                  end
                  return require("luasnip").in_snippet()
                end
              '';

            jump =
              helpers.mkRaw
              # lua
              ''
                function(direction)
                  require("luasnip").jump(direction)
                end
              '';
          };
        };
      };
    };

    extraConfigLuaPost =
      /*
      lua
      */
      ''
        -- Add custom snippets
        local ls = require("luasnip")
        ls.add_snippets("all", {
          ls.snippet("todo", { ls.text_node("TODO(dbalatero): ") }),
        })
      '';
  };
}
