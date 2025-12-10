local resolvePath = require("utils.resolve-path")

-- Sony WH-1000XM4
local headphoneDeviceId = "94-db-56-47-6a-86"

-- Override preferred devices by hostname.

local function getDeviceId()
  local deviceOverrides = {
    -- Work WH-1000XM5 headphones
    ambient = "88-c9-e8-59-08-81",
    jaguar = "88-c9-e8-59-08-81",
    ["st-dbalatero1"] = "88-c9-e8-59-08-81",
  }

  return deviceOverrides[hs.host.localizedName()] or headphoneDeviceId
end

local blueUtil = resolvePath({
  os.getenv("HOME") .. "/.nix-profile/bin/blueutil",
  "/opt/homebrew/bin/blueutil",
  "/usr/local/bin/blueutil",
})

local function disconnectHeadphones()
  hs.task
    .new(blueUtil, function(exitCode, stdout, stderr)
      if exitCode == 0 then
        p("Unpaired device: " .. getDeviceId() .. " with " .. blueUtil)
        hs.alert("Disconnected headphones")
      else
        p("Failed to disconnect: " .. stderr)
        hs.alert("Failed to disconnect: " .. stderr)
      end
    end, {
      "--disconnect",
      getDeviceId(),
    })
    :start()
end

local function connectHeadphones()
  hs.task
    .new(blueUtil, function(exitCode, stdout, stderr)
      if exitCode == 0 then
        p("Paired device: " .. getDeviceId() .. " with " .. blueUtil)
        hs.alert("Connected headphones")
      else
        p("Failed to connect: " .. stderr)
        hs.alert("Failed to connect: " .. stderr)
      end
    end, {
      "--connect",
      getDeviceId(),
    })
    :start()
end

local function checkHeadphonesConnected(fn)
  hs.task
    .new(blueUtil, function(_, stdout)
      stdout = string.gsub(stdout, "\n$", "")
      local isConnected = stdout == "1"

      fn(isConnected)
    end, {
      "--is-connected",
      getDeviceId(),
    })
    :start()
end

local function toggleHeadphones()
  checkHeadphonesConnected(function(isConnected)
    if isConnected then
      disconnectHeadphones()
    else
      connectHeadphones()
    end
  end)
end

hyperKey:bind("b"):toFunction("Toggle 🎧 connection", toggleHeadphones)
