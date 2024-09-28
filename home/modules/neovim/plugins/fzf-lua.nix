{pkgs, ...}: let
  actions = func: {__raw = ''require("fzf-lua.actions").${func}'';};
in {
  home.packages = with pkgs; [
    proximity-sort
  ];

  programs.nixvim = {
    plugins.fzf-lua = {
      enable = true;

      profile = "telescope";

      settings = {
        fzf_color = true;

        winopts = {
          preview = {
            layout = "vertical";
          };
        };

        files = {
          file_icons = false;
          # pay-server can't take the heat
          git_icons = false;

          actions = {
            "enter" = [(actions "file_edit_or_qf")];
            "ctrl-x" = [(actions "file_split")];
            "ctrl-v" = [(actions "file_vsplit")];
            "ctrl-t" = [(actions "file_tabedit")];
            "ctrl-q" = [(actions "file_sel_to_qf")];
            "ctrl-Q" = [(actions "file_sel_to_ll")];
          };
        };

        git = {
          file_icons = false;
          git_icons = false;
        };

        grep = {
          file_icons = false;
          git_icons = false;
        };
      };

      keymaps = {
        "<leader>sb" = {
          action = "buffers";
          options = {
            desc = "FZF: Switch buffers";
            silent = true;
          };
          settings = {
            sort_mru = true;
            sort_lastused = true;
          };
        };

        "<leader>sg" = {
          action = "live_grep";
          options = {
            desc = "FZF: Grep files";
            silent = true;
          };
        };

        "<leader>sm" = {
          action = "marks";
          options = {
            desc = "FZF: Search marks";
            silent = true;
          };
        };

        "<leader>sw" = {
          action = "grep_cword";
          options = {
            desc = "FZF: Grep for current word";
            silent = true;
          };
        };
      };
    };

    extraConfigLuaPost =
      # lua
      ''
        local function FZFPromixitySort()
          local rg_command = "rg --files --hidden --glob '!{node_modules/*,.git/*,.aws/*,.yarn/*}'"
          local base = vim.api.nvim_eval("fnamemodify(expand('%'), ':h:.:S')")
          local command = nil

          if base == "." then
            command = rg_command
          else
            local file = vim.api.nvim_eval("expand('%')")
            command = rg_command .. " | proximity-sort " .. file
          end

          return require("fzf-lua").fzf_exec(command, {
            actions = require('fzf-lua').defaults.actions.files,
            previewer = require('fzf-lua').defaults.previewers.bat
          })
        end

        vim.keymap.set(
          "n",
          "<leader><space>",
          FZFPromixitySort,
          { desc = "FZF: Find files" }
        )
      '';
  };
}
