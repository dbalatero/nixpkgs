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

            local cargo_root_for_buffer = function(bufnr)
              local filename = vim.api.nvim_buf_get_name(bufnr)
              if filename == "" then
                return nil
              end

              local cargo_toml = vim.fs.find("Cargo.toml", {
                upward = true,
                path = vim.fs.dirname(filename),
              })[1]

              if cargo_toml == nil then
                return nil
              end

              return vim.fs.dirname(cargo_toml)
            end

            local tmux_display = function(args)
              local output = vim.fn.system(vim.list_extend({
                "tmux",
                "display-message",
                "-p",
              }, args))

              if vim.v.shell_error ~= 0 then
                return nil
              end

              return vim.trim(output)
            end

            local run_in_bottom_right_pane = function(command)
              if vim.env.TMUX == nil then
                return false
              end

              local current_pane = tmux_display({"#{pane_id}"})
              local target_pane = tmux_display({"-t", "{bottom-right}", "#{pane_id}"})
              if target_pane == nil or target_pane == "" or target_pane == current_pane then
                return false
              end

              vim.fn.system({
                "tmux",
                "send-keys",
                "-t",
                target_pane,
                "C-u",
                command,
                "C-m",
              })

              return vim.v.shell_error == 0
            end

            local run_cargo_command = function(command)
              local cargo_root = cargo_root_for_buffer(event.buf)
              if cargo_root == nil then
                vim.notify("No Cargo.toml found for current buffer", vim.log.levels.WARN)
                return
              end

              vim.cmd.write()
              local tmux_command = "(cd " .. vim.fn.shellescape(cargo_root) .. " && " .. command .. ")"
              if not run_in_bottom_right_pane(tmux_command) then
                vim.fn.VimuxRunCommand(tmux_command)
              end
            end

            local build_cargo_run_command = function()
              local cargo_root = cargo_root_for_buffer(event.buf)
              if cargo_root == nil then
                return "cargo run"
              end

              local filename = vim.api.nvim_buf_get_name(event.buf)
              local relative_filename = vim.fs.relpath(cargo_root, filename)
              if relative_filename == nil then
                return "cargo run"
              end

              local bin_name = relative_filename:match("^src/bin/([^/%.]+)%.[^/]+$")
                or relative_filename:match("^src/bin/([^/]+)/main%.[^/]+$")

              if bin_name == nil then
                return "cargo run"
              end

              return "cargo run --bin " .. vim.fn.shellescape(bin_name)
            end

            vim.keymap.set("n", "<leader>rr", function()
              run_cargo_command(build_cargo_run_command())
            end, opts("Rust: cargo run"))

            vim.keymap.set("n", "<leader>rb", function()
              run_cargo_command("cargo build")
            end, opts("Rust: cargo build"))

            vim.keymap.set("n", "<leader>rc", function()
              run_cargo_command("cargo check")
            end, opts("Rust: cargo check"))

            vim.keymap.set("n", "<leader>rt", function()
              run_cargo_command("cargo test")
            end, opts("Rust: cargo test"))
          end,
        })
      '';
  };
}
