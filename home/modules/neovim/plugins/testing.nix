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

          if !has_key(test#custom_runners, 'typescript')
            let test#custom_runners['typescript'] = []
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
          call add(test#custom_runners['typescript'], "jest")

          " Enable the runners we want
          call add(test#enabled_runners, "lua#busted")
          call add(test#enabled_runners, "ruby#rspec")
          call add(test#enabled_runners, "javascript#jest")
        ]])
      '';
  };
}
