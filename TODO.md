# Neovim Migration TODO

## High Priority Changes

### LSP & Formatting

- [ ] **Add format-ts-errors.nvim** (SKIPPED - plugin not available at specified commit)
  - **Git commit**: `269c1fa` - "feat: typescript error formatting"
  - Prettier TypeScript error messages
  - Dependency for typescript-tools
  - Custom diagnostic handler integration
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/init.lua:28`
  - Location to add: `home/modules/pde/neovim/plugins/lsp.nix`
  - **Note**: Repository returned 404. May need to find working commit or use nixpkgs version.

- [ ] **Add troublesum.nvim dependency** (SKIPPED - plugin not available at specified commits)
  - **Git commit**: `6a8211e` - "feat: more lsp"
  - Shows diagnostic counts in trouble.nvim
  - See: `/home/dbalatero/dotfiles/nvim/lua/packages/lsp/init.lua:51`
  - Location to add: `home/modules/pde/neovim/plugins/lsp.nix`
  - **Note**: Repository returned 404 for both commits tried. May need to find working commit or use nixpkgs version.

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

- [ ] **Sync treesitter language list**
  - dotfiles ensures: bash, css, dockerfile, go, graphql, java, javascript, json, lua, nix, php, python, regex, ruby, tsx, typescript, vim, yaml
  - Nix config should auto-install based on nixvim defaults
  - Verify all languages from dotfiles are available

### Plugin Version Management

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

## Notes

### Architecture Differences
- **dotfiles**: Uses lazy.nvim package manager
- **Nix config**: Uses nixvim (declarative Nix-based config)

These are fundamentally different approaches. The Nix config cannot directly "import" lazy.nvim plugins, but can achieve the same functionality through nixvim's plugin system.

### Recent Major Additions (from git log)
The evolution path from basic config to current state:

1. **flash.nvim** (commit: `67d0d2d`) - Enhanced navigation
1. **ts-comments, todo-comments, noice** (commit: `e0d9a02`) - Modern UI and commenting
1. **blink.cmp** (commit: `b41ca95`) - Completion system upgrade
1. **Claude Code** (commit: `427d561`) - AI integration

These represent the evolution path from the basic config (where the Nix repo likely started) to the current state.

### Commit Analysis Summary

**Total Commits Analyzed**: 47 commits in dotfiles/nvim

**Matched to TODO Items**: 18+ commits
**New TODO Items Added**: 4 high-priority items
**Stripe-Specific Items**: 4 items (optional)
**Maintenance Commits**: 13 commits (lock files, generic updates)

All functional changes from the git history have been accounted for in this TODO list.
