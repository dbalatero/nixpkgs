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
            preset = "super-tab";

            # Disable super-tab's default Tab/Shift-Tab so custom handlers work
            "<Tab>" = [];
            "<S-Tab>" = [];

            "<C-space>" = ["show" "show_documentation" "hide_documentation"];
            "<C-e>" = ["hide"];
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
        -- Custom Tab handler for blink.cmp
        local function custom_tab()
          local cmp = require("blink.cmp")

          -- Handle snippet navigation first
          if cmp.snippet_active() then
            return cmp.snippet_forward()
          end

          -- If completion menu is visible, cycle through items
          if cmp.is_visible() then
            return cmp.select_next()
          else
            -- No menu, fallback to regular tab
            return vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Tab>", true, false, true), "n", false)
          end
        end

        -- Custom Shift-Tab handler for blink.cmp
        local function custom_shift_tab()
          local cmp = require("blink.cmp")

          -- Handle snippet navigation first
          if cmp.snippet_active() then
            return cmp.snippet_backward()
          end

          -- If completion menu is visible, cycle backwards
          if cmp.is_visible() then
            return cmp.select_prev()
          else
            -- No menu, fallback to regular shift-tab
            return vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<S-Tab>", true, false, true), "n", false)
          end
        end

        -- Set up custom Tab handlers
        vim.keymap.set("i", "<Tab>", custom_tab, { desc = "Blink: Select next completion" })
        vim.keymap.set("i", "<S-Tab>", custom_shift_tab, { desc = "Blink: Select prev completion" })

        -- Add custom snippets
        local ls = require("luasnip")
        ls.add_snippets("all", {
          ls.snippet("todo", { ls.text_node("TODO(dbalatero): ") }),
        })
      '';
  };
}
