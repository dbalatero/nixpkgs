{
  config,
  pkgs,
  ...
}: let
  helpers = config.lib.nixvim;
in {
  # ImageMagick is required for snacks.nvim image module
  home.packages = with pkgs; [
    imagemagick
  ];

  programs.nixvim = {
    plugins.which-key.settings.spec = [
      {
        __unkeyed-1 = "<leader>a";
        group = "+claude";
      }
    ];

    extraPlugins = with pkgs; [
      # snacks.nvim - required dependency for claudecode and fzf-lua image previews
      (vimUtils.buildVimPlugin {
        name = "snacks.nvim";
        src = fetchFromGitHub {
          owner = "folke";
          repo = "snacks.nvim";
          rev = "v2.30.0";
          hash = "sha256-5m65Gvc6DTE9v7noOfm0+iQjDrqnrXYYV9QPnmr1JGY=";
        };
        # Skip the require check - snacks.nvim has many optional dependencies
        doCheck = false;
      })

      # claudecode.nvim - Claude Code integration
      (vimUtils.buildVimPlugin {
        name = "claudecode.nvim";
        src = fetchFromGitHub {
          owner = "coder";
          repo = "claudecode.nvim";
          rev = "6091df0e8edcdc92526cec23bbb42f63c0bb5ff2";
          hash = "sha256-PmSYIE7j9C2ckJc9wDIm4KCozXP0z1U9TOdItnDyoDQ=";
        };
      })
    ];

    extraConfigLuaPost =
      /*
      lua
      */
      ''
        -- Configure snacks.nvim (required by claudecode and used by fzf-lua for image previews)
        require("snacks").setup({
          terminal = {},  -- Required for claudecode
          image = {},     -- Enable image support for fzf-lua previews
        })

        -- Configure claudecode.nvim
        require("claudecode").setup({
          -- Use default Claude binary from PATH
          -- terminal_cmd = "claude",

          -- Auto-start server
          auto_start = false,

          -- Terminal position
          split_side = "right",

          -- Use snacks.nvim as terminal provider
          provider = "snacks",

          -- Track editor selections for context
          track_selection = true,

          -- Use git root as working directory
          git_repo_cwd = true,
        })

        -- Keybindings
        vim.keymap.set("n", "<leader>ac", "<cmd>ClaudeCode<cr>", {
          desc = "Toggle Claude",
        })

        vim.keymap.set("n", "<leader>af", "<cmd>ClaudeCodeFocus<cr>", {
          desc = "Focus Claude",
        })

        vim.keymap.set("v", "<leader>as", "<cmd>ClaudeCodeSend<cr>", {
          desc = "Send to Claude",
        })

        vim.keymap.set("n", "<leader>aa", "<cmd>ClaudeCodeDiffAccept<cr>", {
          desc = "Accept diff",
        })

        vim.keymap.set("n", "<leader>ad", "<cmd>ClaudeCodeDiffDeny<cr>", {
          desc = "Deny diff",
        })

        vim.keymap.set("n", "<leader>am", "<cmd>ClaudeCodeSelectModel<cr>", {
          desc = "Select model",
        })
      '';
  };
}
