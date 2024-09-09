{ pkgs, ... }:
{
  programs.nixvim = {
    plugins = {
      lualine.enable = true;
      which-key.enable = true;
    };

    extraConfigLuaPost = 
      /*
      lua
      */
      ''
        vim.g.vimfiler_force_overwrite_statusline = 0
        vim.g.vimfiler_as_default_explorer = 1
        vim.g.vimshell_force_overwrite_statusline = 0

        vim.fn["vimfiler#custom#profile"]("default", "context", { safe = 0 })

        -- bind the minus key to show the file explorer in the dir of the current open
        -- buffer's file
        vim.keymap.set(
          { "n" }, 
          "-", 
          ":VimFilerBufferDir<CR>",
          { 
            noremap = true, 
            silent = true, 
            desc = "Navigate to current directory",
          }
        )
      '';

    extraPlugins = with pkgs;
      (
        with vimPlugins; [
          unite-vim
          vimfiler-vim
        ]
      )
      ++ (
        map vimUtils.buildVimPlugin [
          {
            # disable highlights automatically on cursor move
            name = "vim-cool";
            src = fetchFromGitHub {
              owner = "romainl";
              repo = "vim-cool";
              rev = "662e7b11064cbeedad17c45d2fe926e78d3cd0b6";
              hash = "sha256-M91iWqytUR6AldM2H4U/79nX2ba5gN4I/z7m0iltjcY=";
            };
          }
        ]
      );
  };
}
