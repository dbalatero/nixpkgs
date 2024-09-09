{pkgs, ...}: {
  programs.nixvim = {
    plugins = {
      fugitive.enable = true;

      gitsigns = {
        enable = true;
        settings = {
          signs = {
            add.text = "+";
            change.text = "~";
            delete.text = "_";
            topdelete.text = "‾";
            changedelete.text = "~";
          };
        };
      };
    };

    extraPlugins = with pkgs; (
      with vimPlugins; [
        vim-rhubarb
      ]
    );

    extraConfigLuaPost =
      # lua
      ''
        -- Every time you open a git object using fugitive it creates a new buffer.
        -- This means that your buffer listing can quickly become swamped with
        -- fugitive buffers. This prevents this from becoming an issue:
        vim.api.nvim_create_autocmd({ "BufReadPost" }, {
          pattern = { "fugitive://*" },
          callback = function()
            vim.cmd([[set bufhidden=delete]])
          end,
        })

        vim.api.nvim_set_keymap(
          "v",
          "<leader>g",
          ":GBrowse!<CR>",
          { noremap = true, desc = "Copy link to source in Github" }
        )
      '';
  };
}
