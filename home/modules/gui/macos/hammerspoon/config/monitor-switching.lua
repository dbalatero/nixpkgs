local resolvePath = require("utils.resolve-path")

local function getM1DDCBinary()
  return resolvePath({
    os.getenv("HOME") .. "/.nix-profile/bin/m1ddc", -- nix profile
    "/usr/local/bin/m1ddc", -- intel homebrew
    "/opt/homebrew/bin/m1ddc", -- m1 homebrew
    os.getenv("HOME") .. "/.local/bin/m1ddc", -- local install
  })
end

local function switchMonitor()
  -- Common input values:
  -- DisplayPort 1: 15
  -- DisplayPort 2: 16
  -- HDMI 1: 17
  -- HDMI 2: 18
  -- USB-C: 27
  --
  -- See:
  --   https://github.com/waydabber/m1ddc
  local DP_INPUT = 15
  local USB_C_INPUT = 27

  binary = getM1DDCBinary()
  if not binary then
    hs.notify.new({title = "Monitor Switching", informativeText = "m1ddc binary not found"}):send()
    return
  end

  -- Query current input
  local output = hs.execute(binary .. " display 1 get input 2>&1")
  local currentInput = tonumber(output and output:match("%d+"))
  
  -- Toggle between USB-C and DisplayPort
  local targetInput
  if currentInput == USB_C_INPUT then
    targetInput = DP_INPUT
  elseif currentInput == DP_INPUT then
    targetInput = USB_C_INPUT
  else
    -- If we can't determine current input (e.g., returns 0 or nil), 
    -- default to DP since user wants to switch TO DP from USB-C
    targetInput = DP_INPUT
  end

  hs.execute(binary .. " display 1 set input " .. targetInput)
end

hyperKey:bind("w"):toFunction("Switch monitor input", switchMonitor)
