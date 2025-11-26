{
  lib,
  pkgs,
  ...
}: {
  imports = [./plugins];

  home.packages = with pkgs;
    [
      tree-sitter
    ]
    ++ lib.optionals (!pkgs.stdenv.isDarwin) [
      # libgcc
    ];

  programs.bat.enable = true;

  programs.nixvim = {
    enable = true;
    defaultEditor = true;
    viAlias = false;
    vimAlias = true;

    globals = {
      mapleader = " ";
      maplocalleader = " ";

      # Disable perl
      loaded_perl_provider = 0;
    };

    keymaps = [
      # jk for normal mode
      {
        mode = "i";
        key = "jk";
        action = "<Esc>";
        options = {
          silent = true;
          remap = false;
        };
      }

      # Create window splits with vv or ss
      {
        key = "ss";
        action = "<C-w>s";
        options = {remap = false;};
      }
      {
        key = "vv";
        action = "<C-w>v";
        options = {remap = false;};
      }

      # Allow ctrl+z backgrounding in insert mode
      {
        mode = "i";
        key = "<C-Z>";
        action = "<Esc><C-Z>";
        options = {remap = false;};
      }

      # sane regexes
      {
        mode = ["n" "v"];
        key = "/";
        action = "/\\v";
        options = {remap = false;};
      }

      # Remap : to ;
      {
        key = ";";
        action = ":";
        options = {remap = false;};
      }

      # Better default experience
      {
        mode = ["n" "v"];
        key = "<Space>";
        action = "<Nop>";
        options = {silent = true;};
      }
    ];

    opts = {
      # Disable ex mode, it's dumb
      exrc = false;
      ex = false;
      secure = false;

      # Line numbers
      number = true;
      relativenumber = false;

      # Indents
      expandtab = true;
      linebreak = true;
      wrap = false;
      shiftwidth = 2;
      smartindent = true;
      softtabstop = 2;
      tabstop = 2;

      # 80 chars
      textwidth = 80;
      colorcolumn = "81";

      # No swap/backup
      swapfile = false;
      backup = false;
      wb = false;

      # Scrolling
      scrolloff = 8; # Start scrolling when we're 8 lines away from margins
      sidescrolloff = 15;
      sidescroll = 1;

      # Set highlight on search
      hlsearch = false;
      listchars = "tab:▸ ,trail:ـ,extends:➧,eol:¬";

      # Enable mouse
      mouse = "a";

      # Sync clipboard between OS + nvim
      clipboard = "unnamedplus";

      # Enable break indent
      breakindent = true;

      # Undo history
      history = 1000;
      undofile = true;
      undolevels = 1000;

      # Case insensitive searching UNLESS /C or capital in search
      ignorecase = true;
      smartcase = true;

      # Keep sign column on by default
      signcolumn = "yes";

      # Decrease update time
      updatetime = 250;
      timeout = true;
      timeoutlen = 300;

      # 24 bit color
      termguicolors = true;

      # Open splits to the right or below; more natural than the default
      splitright = true;
      splitbelow = true;

      # Minimum window width
      winwidth = 100;

      # Completion opts
      completeopt = "menuone,noselect";
      wildignore = [
        "node_modules/*"
        "vendor/bundle/*"
        "tmp/*"
      ];
    };

    extraConfigLua = ''
      vim.o.undodir = vim.fn.stdpath("data") .. "/backups"

      --  ╭──────────────────────────────────────────────────────────╮
      --  │ Highlight on yank                                        │
      --  │ See `:help vim.highlight.on_yank()`                      │
      --  ╰──────────────────────────────────────────────────────────╯

      local highlight_group = vim.api.nvim_create_augroup("YankHighlight", { clear = true })
      vim.api.nvim_create_autocmd("TextYankPost", {
        callback = function()
          vim.highlight.on_yank()
        end,
        group = highlight_group,
        pattern = "*",
      })

      -- Don't autowrap lines as I type
      vim.cmd([[set formatoptions-=t]])
    '';

    extraConfigLuaPost =
      # lua
      ''
        pcall(loadfile(os.getenv('HOME') .. '/.nvim.extra.lua'))
      '';

    autoCmd = [
      {
        event = ["BufNewFile" "BufRead"];
        pattern = "*.md";
        command = "set wrap";
      }
      {
        event = ["BufNewFile" "BufRead"];
        pattern = "*.md";
        command = "set formatoptions-=t";
      }
    ];
  };
}
