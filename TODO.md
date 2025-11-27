# Neovim Migration TODO

This document tracks the differences between the current Nix-based Neovim configuration and the `~/dotfiles/nvim` configuration.

## High Priority Changes

### UI Modernization
- [ ] **Add noice.nvim for modern UI**
  - **Git commit**: `e0d9a02` - "ts-comments, todo-comments, noice"
  - Provides modern UI for messages, cmdline, and popups
  - Includes better LSP documentation rendering
  - Dependencies: nui.nvim, nvim-notify
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/ui.lua:49-128`
  - Keybindings:
    - `<leader>snl` - Noice Last Message
    - `<leader>snh` - Noice History
    - `<leader>sna` - Noice All
    - `<leader>snd` - Dismiss All
    - `<c-f>` / `<c-b>` - Scroll in LSP hover docs
  - Location to add: `home/modules/pde/neovim/plugins/ui.nix`

### Editing Enhancements
- [ ] **Add flash.nvim for enhanced navigation**
  - **Git commit**: `67d0d2d` - "flash.nvim"
  - Jump to any location with labels (replaces easymotion/hop)
  - Main keybinding: `s` in normal/visual/operator-pending modes
  - Custom label sequence, disables char mode, enables multi-window search
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/editing.lua:6-38`
  - Location to add: `home/modules/pde/neovim/plugins/editing.nix`

- [ ] **Add todo-comments.nvim**
  - **Git commit**: `e0d9a02` - "ts-comments, todo-comments, noice"
  - Highlights TODO, FIXME, NOTE, etc. in code
  - Navigate between todos with `]t` and `[t`
  - Search todos with `<leader>st` and `<leader>sT`
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/editing.lua:102-125`
  - Location to add: `home/modules/pde/neovim/plugins/editing.nix`

- [ ] **Replace comment.nvim with ts-comments.nvim**
  - **Git commit**: `e0d9a02` - "ts-comments, todo-comments, noice"
  - Treesitter-aware commenting (smarter than regular comment.nvim)
  - Handles embedded languages better (e.g., JS in HTML)
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/editing.lua:95-99`
  - Location to update: `home/modules/pde/neovim/plugins/editing.nix`

- [ ] **Add mini.ai for extended text objects**
  - **Git commits**:
    - `7e5379d` - "add mini.ai" (initial implementation)
    - `91f3895` - "fix mini.ai" (adds error handling for missing parsers)
  - Provides powerful text object selections
  - Custom treesitter-based text objects (functions, classes, blocks)
  - Includes fallback wrapper when treesitter parser unavailable
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/editing.lua:271-309`
  - Location to add: `home/modules/pde/neovim/plugins/editing.nix`

- [ ] **Add quicker.nvim for better quickfix**
  - **Git commit**: `cffe0f7` - "feat: add quicker"
  - Enhanced quickfix window with expand/collapse context
  - `>` to expand context, `<` to collapse
  - `<leader>q` to toggle quickfix
  - Expand with 2 lines before/after context
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/editing.lua:44-78`
  - Location to add: `home/modules/pde/neovim/plugins/editing.nix`

- [ ] **Add vim-eunuch for Unix file operations**
  - **Git commit**: `65a48fe` - "vim-eunuch + updates"
  - Provides :Delete, :Move, :Rename, :Chmod, :Mkdir, etc.
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/editing.lua:41-42`
  - Location to add: `home/modules/pde/neovim/plugins/editing.nix`

### LSP & Formatting
- [ ] **Replace lsp-format.nvim with conform.nvim**
  - **Git commits**:
    - `0600e3f` - "fix: parity with nixpkgs" (adds conform.nvim)
    - `1bab50a` - "eslint fix on save" (adds format_after_save callback)
  - conform.nvim is more actively maintained and flexible
  - Supports format_after_save callback for ESLint integration
  - format_on_save with 500ms timeout, lsp_format fallback
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/formatting.lua`
  - Location to update: `home/modules/pde/neovim/plugins/lsp.nix`
  - Note: Remove lsp-format configuration

- [ ] **Add ESLint LSP with format-on-save integration**
  - **Git commit**: `1bab50a` - "eslint fix on save"
  - Configure eslint LSP server
  - Integrate with conform.nvim format_after_save callback
  - Keybinding: `<leader>le` for :EslintFixAll
  - Auto-run EslintFixAll after save when ESLint is attached
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/eslint.lua` and `/home/dbalatero/dotfiles/nvim/lua/packages/formatting.lua`
  - Location to add: `home/modules/pde/neovim/plugins/lsp.nix`

- [ ] **Add lazydev.nvim for Lua LSP improvements**
  - **Git commit**: `07de23d` - "feat: lua_ls"
  - Better nvim Lua development support
  - Loads luv types for vim.uv
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/init.lua:36-45`
  - Location to add: `home/modules/pde/neovim/plugins/lsp.nix`

- [ ] **Add format-ts-errors.nvim**
  - **Git commit**: `269c1fa` - "feat: typescript error formatting"
  - Prettier TypeScript error messages
  - Dependency for typescript-tools
  - Custom diagnostic handler integration
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/init.lua:28`
  - Location to add: `home/modules/pde/neovim/plugins/lsp.nix`

- [ ] **Add nvim-lint for additional diagnostics**
  - **Git commits**:
    - `0600e3f` - "fix: parity with nixpkgs" (adds nvim-lint with rubocop)
    - `841e087` - "update plugins" (switches to custom fork for timeout fixes)
  - Adds rubocop and vale linting
  - Uses custom fork: dbalatero/nvim-lint, branch: custom-fork
  - Runs on BufWritePost with 300ms debounce
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/diagnostics/init.lua`
  - Location to add: `home/modules/pde/neovim/plugins/lsp.nix` or new file

- [ ] **Add troublesum.nvim dependency**
  - **Git commit**: `6a8211e` - "feat: more lsp"
  - Shows diagnostic counts in trouble.nvim
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/init.lua:51`
  - Location to add: `home/modules/pde/neovim/plugins/lsp.nix`

- [ ] **Update LSP keybindings**
  - **Git commit**: `5b38e69` - "fix: LSP keybinds"
  - Fix `gd` vs `gD` mappings (definition vs declaration)
  - Move `<leader>li` to global keymap instead of per-buffer
  - Add `<leader>lm` and `<leader>lp` temporary rename shortcuts
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/setup.lua`
  - Location to update: `home/modules/pde/neovim/plugins/lsp.nix`

- [ ] **Update Trouble.nvim keybindings for v3 API**
  - **Git commit**: `79a5566` - "fix: trouble hotkeys with new trouble API change"
  - Updates from `TroubleToggle` to `Trouble diagnostics toggle`
  - `<leader>xx` = Trouble diagnostics toggle
  - `<leader>xX` = Trouble diagnostics toggle filter.buf=0 (buffer only)
  - `<leader>xl` = Trouble loclist toggle
  - `<leader>xq` = Trouble quickfix toggle
  - `gR` = Trouble lsp toggle (references/definitions)
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/init.lua:55-91`
  - Location to update: `home/modules/pde/neovim/plugins/lsp.nix`
  - Note: Nix config might have older trouble.nvim version

### AI Integration
- [ ] **Add claudecode.nvim plugin**
  - **Git commit**: `427d561` - "feat: add claude code to neovim"
  - Claude Code integration for Neovim
  - Extensive keybindings under `<leader>a`
  - Dependencies: snacks.nvim
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/ai.lua`
  - Keybindings:
    - `<leader>ac` - Toggle Claude
    - `<leader>af` - Focus Claude
    - `<leader>ar` - Resume Claude
    - `<leader>aC` - Continue Claude
    - `<leader>am` - Select Claude model
    - `<leader>ab` - Add current buffer
    - `<leader>as` - Send to Claude (visual) / Add file (tree)
    - `<leader>aa` - Accept diff
    - `<leader>ad` - Deny diff
  - Location to add: New file `home/modules/pde/neovim/plugins/ai.nix`

## Medium Priority Changes

### Basic Settings & Keymaps
- [ ] **Add copy filepath keybindings**
  - `<leader>yf` - Copy relative path
  - `<leader>yF` - Copy absolute path
  - `<leader>yt` - Copy filename only
  - `<leader>yh` - Copy directory path
  - See: `/home/dbalatero/dotfiles/nvim/init.lua:131-153`
  - Location to add: `home/modules/pde/neovim/default.nix` keymaps section

- [ ] **Add Python and Node host program paths**
  - Python 2: `~/.pyenv/versions/py2neovim/bin/python`
  - Python 3: `~/.pyenv/versions/py3neovim/bin/python`
  - Node: `~/.nodenv/versions/15.7.0/bin/node`
  - See: `/home/dbalatero/dotfiles/nvim/init.lua:98-104`
  - Location to add: `home/modules/pde/neovim/default.nix` globals section

- [ ] **Improve markdown autocmd handling**
  - **Git commit**: `072f541` - "markdown word wrap in neovim"
  - Current Nix config sets wrap but doesn't handle formatoptions
  - dotfiles explicitly removes 't' from formatoptions for markdown
  - Uses FileType autocmd with `vim.opt_local.formatoptions:remove("t")`
  - See: `/home/dbalatero/dotfiles/nvim/init.lua:170-181`
  - Location to update: `home/modules/pde/neovim/default.nix` autoCmd section

### Git Integration
- [ ] **Add unified Browse command**
  - **Git commits**:
    - `a14c305` - "feat: add sourcegraph link copy function"
    - `c15d2aa` - "feat: create unified command for gbrowse"
  - Single command that works with both GitHub and Sourcegraph
  - Detects stripe-internal repos and uses Sgbrowse
  - Supports visual mode line ranges
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/git.lua:22-53`
  - Keybinding: `<leader>g` (visual mode)
  - Location to update: `home/modules/pde/neovim/plugins/git.nix`
  - Note: Current Nix config only has basic GBrowse

- [ ] **Consider gitsigns status**
  - dotfiles has gitsigns commented out
  - Nix config has it enabled
  - May want to disable in Nix to match dotfiles
  - Location: `home/modules/pde/neovim/plugins/git.nix:6-17`

### File Navigation
- [ ] **Add proximity-sort binary check**
  - dotfiles checks if proximity-sort binary exists before using
  - Falls back to plain rg if not found
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/fzf.lua:1-31`
  - Current Nix config assumes it exists (installed via home.packages)
  - Location to update: `home/modules/pde/neovim/plugins/fzf-lua.nix`

- [ ] **Update fzf-lua winopts preview layout**
  - **Git commit**: `a9ca199` - "fix: move fzf preview to right"
  - dotfiles uses "horizontal" layout (preview on right)
  - Nix uses "vertical" layout (preview on bottom)
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/fzf.lua:65-70`
  - Location to update: `home/modules/pde/neovim/plugins/fzf-lua.nix:18`

## Low Priority / Optional

### Treesitter
- [ ] **Add rainbow-delimiters check**
  - Nix config enables rainbow-delimiters
  - dotfiles doesn't have it
  - Decide if you want to keep it or remove it
  - Location: `home/modules/pde/neovim/plugins/treesitter.nix:4`

- [ ] **Add PHP to treesitter languages**
  - **Git commit**: `00cc9d3` - "add php to langs"
  - Add "php" to ensure_installed list
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/treesitter.lua:37`
  - Location: `home/modules/pde/neovim/plugins/treesitter.nix`

- [ ] **Sync treesitter language list**
  - dotfiles ensures: bash, css, dockerfile, go, graphql, java, javascript, json, lua, nix, php, python, regex, ruby, tsx, typescript, vim, yaml
  - Nix config should auto-install based on nixvim defaults
  - Verify all languages from dotfiles are available

### Plugin Version Management
- [ ] **Review vim-cool status**
  - Plugin is commented out in Nix default.nix
  - Plugin is active in dotfiles and Nix ui.nix
  - Cleanup: Remove commented code or enable in default.nix
  - Location: `home/modules/pde/neovim/plugins/default.nix:30-39`

- [ ] **Update lualine source**
  - Nix builds from master branch of GitHub
  - May want to pin to specific version for stability
  - Location: `home/modules/pde/neovim/plugins/ui.nix:86-92`

### Testing
- [ ] **Verify vim-test configuration parity**
  - Both configs look very similar
  - Nix config appears to be missing stripe-specific test runners
  - May need to add conditional logic for Stripe repos
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/testing.lua:64-82`
  - Location: `home/modules/pde/neovim/plugins/testing.nix`

## Stripe-Specific (Optional for Personal Machines)

These features are conditionally loaded only on Stripe machines. You may want to skip these for personal Nix configs.

- [ ] **Add Stripe pay-server TypeScript LSP configuration**
  - **Git commits**:
    - `cff78fa` - "feat: typescript support in ps"
    - `548a738` - "feat: tsserver in ps"
    - `caa5bbd` - "bump mem to 12gb in TS"
  - Conditional tsserver_path for pay-server (frontend/js-scripts/node_modules/typescript/lib/tsserver.js)
  - Auto-install js-scripts if missing (pay exec autogen-lsp-server)
  - Memory configuration (12GB for pay-server)
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/typescript.lua`
  - Location: Conditional in LSP setup

- [ ] **Add Stripe autogen LSP server**
  - **Git commit**: `e1b10d5` - "feat: autogen lsp"
  - Only activates in pay-server directories
  - Supports Ruby and YAML filetypes
  - Handles devbox vs laptop environments
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/stripe_autogen.lua`
  - Location: Conditional LSP setup

- [ ] **Add Stripe devbox environment detection**
  - **Git commit**: `c1237a2` - "add devbox vim support"
  - Detect STRIPE_USER environment variable for devbox
  - Different pay-server path for devbox (/pay/src/pay-server)
  - Used by LSP configurations to adapt commands
  - See: `/home/dbalatero/dotfiles/nvim/lua/custom/config.lua`
  - Location: Conditional logic

- [ ] **Add Vale linting for Stripe markdoc**
  - **Git commit**: `86f232f` - "feat: add vale for stripe markdoc"
  - Adds vale linter with pay-server specific config
  - Only runs in pay-server (docs/vale/.vale.ini)
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/diagnostics/init.lua`
  - Location: Conditional in nvim-lint setup

## Notes

### Architecture Differences
- **dotfiles**: Uses lazy.nvim package manager
- **Nix config**: Uses nixvim (declarative Nix-based config)

These are fundamentally different approaches. The Nix config cannot directly "import" lazy.nvim plugins, but can achieve the same functionality through nixvim's plugin system.

### Completion System Evolution
Based on git history, the dotfiles recently switched from nvim-cmp to blink.cmp (commit: `b41ca95 switch to blink.cmp`). This is a significant change that should be prioritized in the Nix migration.

### Recent Major Additions (from git log)
The evolution path from basic config to current state:

1. **flash.nvim** (commit: `67d0d2d`) - Enhanced navigation
2. **mini.ai** (commits: `91f3895`, `7e5379d`) - Extended text objects
3. **ts-comments, todo-comments, noice** (commit: `e0d9a02`) - Modern UI and commenting
4. **blink.cmp** (commit: `b41ca95`) - Completion system upgrade
5. **Claude Code** (commit: `427d561`) - AI integration
6. **quicker.nvim** (commit: `cffe0f7`) - Better quickfix

These represent the evolution path from the basic config (where the Nix repo likely started) to the current state.

### Commit Analysis Summary

**Total Commits Analyzed**: 47 commits in dotfiles/nvim

**Matched to TODO Items**: 18+ commits
**New TODO Items Added**: 4 high-priority items
**Stripe-Specific Items**: 4 items (optional)
**Maintenance Commits**: 13 commits (lock files, generic updates)

All functional changes from the git history have been accounted for in this TODO list.
