--  ╭──────────────────────────────────────────────────────────╮
--  │   LSP Configuration & Plugins                            │
--  ╰──────────────────────────────────────────────────────────╯

-- Use internal formatting for bindings like gq.
vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(args)
    vim.bo[args.buf].formatexpr = nil
  end,
})

local function filter(arr, fn)
  if type(arr) ~= "table" then
    return arr
  end

  local filtered = {}
  for k, v in pairs(arr) do
    if fn(v, k, arr) then
      table.insert(filtered, v)
    end
  end

  return filtered
end

local function typescript_on_definition_list(options)
  local items = options.items

  if #items > 1 then
    items = filter(items, function(definition)
      return string.match(definition.filename, "node_modules") == nil
    end)
  end

  vim.fn.setqflist({}, " ", { title = options.title, items = items, context = options.context })
  vim.api.nvim_command("cfirst") -- or maybe you want 'copen' instead of 'cfirst'
end

return {
  {
    "rafamadriz/friendly-snippets",
    dependencies = { "L3MON4D3/LuaSnip" },
    config = function()
      require("luasnip.loaders.from_vscode").lazy_load()
    end,
  },

  {
    "neovim/nvim-lspconfig",
    dependencies = {
      -- Automatically install LSPs to stdpath for neovim
      "williamboman/mason.nvim",
      "williamboman/mason-lspconfig.nvim",

      -- Useful status updates for LSP
      -- Standalone UI for nvim-lsp progress
      -- NOTE: `opts = {}` is the same as calling `require('fidget').setup({})`
      {
        "j-hui/fidget.nvim",
        tag = "legacy", -- Apparently they are rewriting the plugin
        config = function()
          require("fidget").setup({
            sources = {
              ["null-ls"] = {
                ignore = true,
              },
            },
            timer = {
              task_decay = 400,
              fidget_decay = 700,
            },
          })
        end,
      },

      -- Improve any TypeScript projects
      "jose-elias-alvarez/typescript.nvim",

      -- Autoinstall null-ls formatters
      {
        "jay-babu/mason-null-ls.nvim",
        event = { "BufReadPre", "BufNewFile" },
        dependencies = {
          "williamboman/mason.nvim",
          "jose-elias-alvarez/null-ls.nvim",
          "lukas-reineke/lsp-format.nvim",
        },
      },

      -- Additional lua configuration, makes nvim stuff amazing!
      "folke/neodev.nvim",

      -- Diagnostics
      {
        "ivanjermakov/troublesum.nvim",
        config = function()
          require("troublesum").setup()
        end,
      },
      {
        "folke/trouble.nvim",
        dependencies = {
          "kyazdani42/nvim-web-devicons",
        },
        config = function()
          require("trouble").setup({
            use_diagnostic_signs = true,
          })

          vim.keymap.set(
            "n",
            "<leader>xx",
            "<cmd>TroubleToggle<cr>",
            { silent = true, noremap = true }
          )
          vim.keymap.set(
            "n",
            "<leader>xw",
            "<cmd>TroubleToggle workspace_diagnostics<cr>",
            { silent = true, noremap = true }
          )
          vim.keymap.set(
            "n",
            "<leader>xd",
            "<cmd>TroubleToggle document_diagnostics<cr>",
            { silent = true, noremap = true }
          )
          vim.keymap.set(
            "n",
            "<leader>xl",
            "<cmd>TroubleToggle loclist<cr>",
            { silent = true, noremap = true }
          )
          vim.keymap.set(
            "n",
            "<leader>xq",
            "<cmd>TroubleToggle quickfix<cr>",
            { silent = true, noremap = true }
          )
          vim.keymap.set(
            "n",
            "gR",
            "<cmd>TroubleToggle lsp_references<cr>",
            { silent = true, noremap = true }
          )

          -- More keybinds
          vim.keymap.set("n", "gk", function()
            vim.diagnostic.goto_prev({ severity = vim.diagnostic.severity.ERROR })
          end, { desc = "Go to previous error message" })

          vim.keymap.set(
            "n",
            "g<",
            vim.diagnostic.goto_prev,
            { desc = "Go to previous diagnostic" }
          )

          vim.keymap.set("n", "gj", function()
            vim.diagnostic.goto_next({ severity = vim.diagnostic.severity.ERROR })
          end, { desc = "Go to next error message" })

          vim.keymap.set("n", "g>", vim.diagnostic.goto_next, { desc = "Go to next diagnostic" })

          vim.keymap.set(
            "n",
            "<leader>e",
            vim.diagnostic.open_float,
            { desc = "Open floating diagnostic message" }
          )
          vim.keymap.set(
            "n",
            "<leader>q",
            vim.diagnostic.setloclist,
            { desc = "Open diagnostics list" }
          )

          -- temporary
          vim.keymap.set("n", "<leader>lp", function()
            local var_name = vim.fn.expand("<cWORD>")
            if var_name:match("_") ~= nil then
              vim.lsp.buf.rename("_args")
            else
              vim.lsp.buf.rename("args")
            end
          end, { desc = "Rename params -> args" })

          vim.keymap.set("n", "<leader>lm", function()
            vim.lsp.buf.rename("TMutationArgs")
          end, { desc = "Rename mutation" })
        end,
      },
    },
    config = function()
      local lsp_format = require("lsp-format")
      lsp_format.setup()

      --  This function gets run when an LSP connects to a particular buffer.
      local on_attach = function(client, bufnr)
        lsp_format.on_attach(client)

        -- NOTE: Remember that lua is a real programming language, and as such it is possible
        -- to define small helper and utility functions so you don't have to repeat yourself
        -- many times.
        --
        -- In this case, we create a function that lets us more easily define mappings specific
        -- for LSP related items. It sets the mode, buffer and description for us each time.
        local map = function(modes, keys, func, desc)
          if desc then
            desc = "LSP: " .. desc
          end

          vim.keymap.set(modes, keys, func, { buffer = bufnr, desc = desc })
        end

        local nmap = function(keys, func, desc)
          return map("n", keys, func, desc)
        end

        local nvmap = function(keys, func, desc)
          return map({ "n", "v" }, keys, func, desc)
        end

        nmap("<leader>li", ":LspInfo<CR>", "[I]nfo")
        nmap("<leader>lr", vim.lsp.buf.rename, "[R]ename")
        nvmap("<leader>lc", vim.lsp.buf.code_action, "[C]ode Action")
        nmap("<leader>lx", ":LspRestart<CR>", "Restart LSP in buffer")

        nmap("gd", function()
          vim.lsp.buf.definition({ on_list = typescript_on_definition_list })
        end, "[G]oto [D]efinition")
        nmap("gr", require("telescope.builtin").lsp_references, "[G]oto [R]eferences")
        nmap("gI", vim.lsp.buf.implementation, "[G]oto [I]mplementation")
        nmap("<leader>D", vim.lsp.buf.type_definition, "Type [D]efinition")
        nmap("<leader>ld", require("telescope.builtin").lsp_document_symbols, "[D]ocument Symbols")
        nmap(
          "<leader>lws",
          require("telescope.builtin").lsp_dynamic_workspace_symbols,
          "[W]orkspace [S]ymbols"
        )

        -- See `:help K` for why this keymap
        nmap("K", vim.lsp.buf.hover, "Hover Documentation")
        -- TODO: find another key
        -- nmap('<C-k>', vim.lsp.buf.signature_help, 'Signature Documentation')

        -- Lesser used LSP functionality
        nmap("gD", vim.lsp.buf.declaration, "[G]oto [D]eclaration")
        nmap("<leader>lwa", vim.lsp.buf.add_workspace_folder, "[W]orkspace [A]dd Folder")
        nmap("<leader>lwr", vim.lsp.buf.remove_workspace_folder, "[W]orkspace [R]emove Folder")
        nmap("<leader>lwl", function()
          print(vim.inspect(vim.lsp.buf.list_workspace_folders()))
        end, "[W]orkspace [L]ist Folders")

        -- Create a command `:Format` local to the LSP buffer
        vim.api.nvim_buf_create_user_command(bufnr, "Format", function(_)
          vim.lsp.buf.format()
        end, { desc = "Format current buffer with LSP" })
      end

      -- Enable the following language servers
      --  Feel free to add/remove any LSPs that you want here. They will automatically be installed.
      --
      --  Add any additional override configuration in the following tables. They will be passed to
      --  the `settings` field of the server config. You must look up that documentation yourself.
      local servers = {
        bashls = {},
        jsonls = {
          json = {
            schemas = {
              {
                description = "TypeScript compiler configuration file",
                fileMatch = { "tsconfig.json", "tsconfig.*.json" },
                url = "http://json.schemastore.org/tsconfig",
              },
              {
                description = "Babel configuration",
                fileMatch = { ".babelrc.json", ".babelrc", "babel.config.json" },
                url = "http://json.schemastore.org/lerna",
              },
              {
                description = "ESLint config",
                fileMatch = { ".eslintrc.json", ".eslintrc" },
                url = "http://json.schemastore.org/eslintrc",
              },
              {
                description = "Prettier config",
                fileMatch = { ".prettierrc", ".prettierrc.json", "prettier.config.json" },
                url = "http://json.schemastore.org/prettierrc",
              },
              {
                description = "Vercel Now config",
                fileMatch = { "now.json" },
                url = "http://json.schemastore.org/now",
              },
              {
                description = "Stylelint config",
                fileMatch = { ".stylelintrc", ".stylelintrc.json", "stylelint.config.json" },
                url = "http://json.schemastore.org/stylelintrc",
              },
            },
          },
        },
        lua_ls = {
          Lua = {
            workspace = { checkThirdParty = false },
            telemetry = { enable = false },
          },
        },
        rust_analyzer = {
          ["rust-analyzer"] = {
            assist = {
              importGranularity = "module",
              importPrefix = "by_self",
            },
            cargo = {
              loadOutDirsFromCheck = true,
            },
            procMacro = {
              enable = true,
            },
          },
        },
        tsserver = {},
        yamlls = {
          yaml = {
            schemas = {
              -- Github actions
              ["https://json.schemastore.org/github-workflow"] = ".github/workflows/*.{yml,yaml}",
              ["https://json.schemastore.org/github-action"] = ".github/action.{yml,yaml}",
            },
          },
        },
      }

      -- Setup neovim lua configuration
      require("neodev").setup({
        library = {
          enabled = true,
          plugins = { "nvim-dap-ui" },
          runtime = true,
          types = true,
        },
        lspconfig = true,
        pathStrict = true,
        setup_jsonls = true,
      })

      -- nvim-cmp supports additional completion capabilities, so broadcast that to servers
      local capabilities = vim.lsp.protocol.make_client_capabilities()
      capabilities = require("cmp_nvim_lsp").default_capabilities(capabilities)

      -- Setup mason so it can manage external tooling
      require("mason").setup()

      -- Ensure the servers above are installed
      local mason_lspconfig = require("mason-lspconfig")

      mason_lspconfig.setup({
        ensure_installed = vim.tbl_keys(servers),
      })

      local lspconfig = require("lspconfig")

      -- Sorbet needs to be set up manually...
      lspconfig.sorbet.setup({
        capabilities = capabilities,
        on_attach = on_attach,
        settings = {},
        root_dir = lspconfig.util.root_pattern("sorbet"),
      })

      mason_lspconfig.setup_handlers({
        -- Default setup handler
        function(server_name)
          lspconfig[server_name].setup({
            capabilities = capabilities,
            on_attach = on_attach,
            settings = servers[server_name],
          })
        end,
        tsserver = function()
          lspconfig.tsserver.setup({
            cmd_env = { NODE_OPTIONS = "--max-old-space-size=8192" }, -- Give 8gb of RAM to node
            filetypes = {
              "javascript",
              "javascriptreact",
              "typescript",
              "typescriptreact",
              "typescript.tsx",
            },
            init_options = {
              maxTsServerMemory = "8192",
              preferences = {
                -- Ensure we always import from relative paths
                -- Can be 'auto' | 'relative' | 'non-relative'
                importModuleSpecifierPreference = "relative",
              },
            },
            root_dir = lspconfig.util.root_pattern("tsconfig.json"),
            on_attach = function(client, bufnr)
              client.server_capabilities.documentFormattingProvider = false
              client.server_capabilities.documentRangeFormattingProvider = false

              if client.config.flags then
                client.config.flags.allow_incremental_sync = true
              end

              on_attach(client, bufnr)
            end,
          })
        end,
      })

      local ignorePrettierRules = function(diagnostic)
        return diagnostic.code ~= "prettier/prettier"
      end

      local getDirectoryContaining = function(filepath, containingFile)
        local directory = vim.fs.dirname(filepath)
        local found_dir = vim.fn.findfile(containingFile, directory .. ";")

        if found_dir then
          return vim.fs.dirname(found_dir)
        else
          return nil
        end
      end

      -- given a filepath = "path/to/blah.js"
      local findNearestEslintConfigDir = function(filepath)
        return getDirectoryContaining(filepath, ".eslintrc.js")
      end

      local isMonorepo = function()
        return vim.fn.getcwd():match("code/monologue") ~= nil
      end

      local hasEslintConfig = function(utils)
        return isMonorepo()
          or utils.root_has_file({
            ".eslintrc",
            ".eslintrc.json",
            ".eslintrc.js",
          })
      end

      local getRepoRoot = function(filepath)
        return getDirectoryContaining(filepath, ".git")
      end

      local isNotMonorepo = function(utils)
        return not isMonorepo() and hasEslintConfig(utils)
      end

      local eslintCwd = function(params)
        return findNearestEslintConfigDir(params.bufname) or nil
      end

      local standardEslintConfig = {
        condition = isNotMonorepo,
        cwd = eslintCwd,
        filter = ignorePrettierRules,
      }

      local null_ls = require("null-ls")

      local monologueEslint = {
        cwd = eslintCwd,
        env = function(params)
          return {
            -- NODE_OPTIONS = "--require " .. params.root .. "/.pnp.cjs",
          }
        end,
      }

      null_ls.setup({
        debug = true, -- log_level = trace, basically
        capabilities = capabilities,
        on_attach = on_attach,
        sources = {
          --  ╭──────────────────────────────────────────────────────────╮
          --  │     Lua                                                  │
          --  ╰──────────────────────────────────────────────────────────╯
          null_ls.builtins.formatting.stylua,

          --  ╭──────────────────────────────────────────────────────────╮
          --  │     Ruby                                                 │
          --  ╰──────────────────────────────────────────────────────────╯
          null_ls.builtins.formatting.rubyfmt,

          --  ╭──────────────────────────────────────────────────────────╮
          --  │     TypeScript                                           │
          --  ╰──────────────────────────────────────────────────────────╯
          null_ls.builtins.formatting.prettierd,

          -- null_ls.builtins.diagnostics.eslint.with({
          --   dynamic_command = require("null-ls.helpers.command_resolver").from_yarn_pnp(),
          --   conditions = function(utils)
          --     return utils.root_has_file({ ".pnp.cjs" })
          --   end,
          -- }),

          null_ls.builtins.code_actions.eslint_d.with(monologueEslint),
          null_ls.builtins.diagnostics.eslint_d.with(monologueEslint),
          null_ls.builtins.formatting.eslint_d.with(monologueEslint),

          -- null_ls.builtins.diagnostics.eslint.with({
          --   command = "yarn",
          --   args = {
          --     "eslint",
          --     "--cache",
          --     "-f",
          --     "json",
          --     "--stdin",
          --     "--stdin-filename",
          --     "$FILENAME",
          --   },
          --   cwd = eslintCwd,
          --   -- filter = ignorePrettierRules,
          -- }),

          -- null_ls.builtins.diagnostics.eslint.with({
          --   dynamic_command = function()
          --     return "yarn run eslint"
          --   end,
          --   condition = isMonorepo,
          --   cwd = eslintCwd,
          --   filter = ignorePrettierRules,
          -- }),
          --
          -- null_ls.builtins.code_actions.eslint_d.with(standardEslintConfig),
          -- null_ls.builtins.diagnostics.eslint_d.with(standardEslintConfig),
        },
      })

      require("mason-null-ls").setup({
        ensure_installed = nil,
        automatic_installation = true,
        automatic_setup = false,
      })
    end,
  },
}
