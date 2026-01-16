vim.opt.clipboard:append("unnamedplus")
vim.g.mapleader = " "

-- ╭─────────────────────────────────────────────────────────╮
-- │ Fast vertical/horizontal splits                         │
-- ╰─────────────────────────────────────────────────────────╯
vim.keymap.set({ "n" }, "vv", function()
  vim.cmd([[call VSCodeNotify('workbench.action.splitEditorRight')]])
end)

vim.keymap.set({ "n" }, "ss", function()
  vim.cmd([[call VSCodeNotify('workbench.action.splitEditorDown')]])
end)

-- ╭─────────────────────────────────────────────────────────╮
-- │ Jump to previous/next diagnostic errors                 │
-- ╰─────────────────────────────────────────────────────────╯
vim.keymap.set({ "n" }, "gj", function()
  vim.cmd([[call VSCodeNotify('editor.action.marker.next')]])
end)

vim.keymap.set({ "n" }, "gk", function()
  vim.cmd([[call VSCodeNotify('editor.action.marker.prev')]])
end)

-- ╭─────────────────────────────────────────────────────────╮
-- │ Panel navigation                                        │
-- ╰─────────────────────────────────────────────────────────╯
vim.keymap.set({ "n" }, "<leader>a", function()
  vim.cmd([[call VSCodeNotify('workbench.action.focusAuxiliaryBar')]])
end)

vim.keymap.set({ "n" }, "<leader>e", function()
  vim.cmd([[call VSCodeNotify('workbench.action.focusSideBar')]])
end)

vim.keymap.set({ "n" }, "<leader><leader>", function()
  vim.cmd([[call VSCodeNotify('workbench.action.quickOpen')]])
end)
