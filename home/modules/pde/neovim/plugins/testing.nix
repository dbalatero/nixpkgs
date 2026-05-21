{pkgs, ...}: {
  programs.nixvim = {
    extraPlugins = with pkgs; (
      with vimPlugins; [
        vim-test
        vimux
      ]
    );

    extraConfigLua =
      # lua
      ''
        vim.cmd([[
          if !exists('test#custom_runners')
            let test#custom_runners = {}
          endif

          if !has_key(test#custom_runners, 'lua')
            let test#custom_runners['lua'] = []
          endif

          if !has_key(test#custom_runners, 'ruby')
            let test#custom_runners['ruby'] = []
          endif

          if !has_key(test#custom_runners, 'javascript')
            let test#custom_runners['javascript'] = []
          endif

          if !exists("test#enabled_runners")
            let test#enabled_runners = []
          endif
        ]])
      '';

    extraConfigLuaPost =
      # lua
      ''
        -- TODO: convert -> Lua someday or like never who cares
        vim.cmd([[
          nmap <silent> <leader>T :TestNearest<CR>
          nmap <silent> <leader>t :TestFile<CR>

          let g:test#preserve_screen = 1
          let g:VimuxOrientation = "h"
          let g:VimuxRunnerQuery = {'pane': '{bottom-right}'}
          let test#neovim#term_position = "vert"
          let test#vim#term_position = "vert"

          let g:test#javascript#mocha#file_pattern = '\v.*_test\.(js|jsx|ts|tsx)$'

          if exists('$TMUX')
            " Use tmux to kick off tests if we are in tmux currently
            let test#strategy = 'vimux'
          else
            " Fallback to using terminal split
            let test#strategy = "neovim"
          endif

          " Define the runners
          call add(test#custom_runners['lua'], "busted")
          call add(test#custom_runners['ruby'], "rspec")
          call add(test#custom_runners['javascript'], "jest")

          " Enable the runners we want
          call add(test#enabled_runners, "lua#busted")
          call add(test#enabled_runners, "ruby#rspec")
          call add(test#enabled_runners, "javascript#jest")
        ]])

        vim.api.nvim_create_autocmd("FileType", {
          pattern = "rust",
          callback = function(event)
            local opts = function(desc)
              return {
                buffer = event.buf,
                desc = desc,
              }
            end

            vim.keymap.set("n", "<leader>rr", function()
              vim.fn.VimuxRunCommand("cargo run")
            end, opts("Rust: cargo run"))

            vim.keymap.set("n", "<leader>rb", function()
              vim.fn.VimuxRunCommand("cargo build")
            end, opts("Rust: cargo build"))

            vim.keymap.set("n", "<leader>rt", function()
              vim.fn.VimuxRunCommand("cargo test")
            end, opts("Rust: cargo test"))
          end,
        })
      '';
  };
}
