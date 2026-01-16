vim.opt.clipboard:append("unnamedplus")

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
