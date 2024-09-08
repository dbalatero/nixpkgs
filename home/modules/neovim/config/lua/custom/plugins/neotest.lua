--  ╭──────────────────────────────────────────────────────────╮
--  │ Neotest                                                  │
--  ╰──────────────────────────────────────────────────────────╯
return {
  {
    "nvim-neotest/neotest",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-treesitter/nvim-treesitter",
      "antoinemadec/FixCursorHold.nvim",

      -- Languages
      "haydenmeade/neotest-jest",
      "nvim-neotest/nvim-nio",
    },
    config = function()
      require("neotest").setup({
        adapters = {
          require("neotest-jest")({}),
        },
      })
    end,
  },
}
