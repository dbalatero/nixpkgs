local function getChromeUrl()
  local application = hs.application.frontmostApplication()

  if application:bundleID() ~= "com.google.Chrome" then
    return nil
  end

  local _, url = hs.osascript.applescript([[
    tell application "Google Chrome"
      get URL of active tab of front window
    end tell
  ]])

  return url
end

local function setChromeUrl(newUrl)
  local script = [[
    const chrome = Application('Google Chrome');
    let activeTab = null;
    let minIndex = 99999999999999999;

    chrome.windows().forEach((window) => {
      const index = window.index();

      if (index < minIndex) {
        minIndex = index;
        activeTab = window.activeTab;
      }
    });
  ]]

  script = script .. "\n" .. 'activeTab.url = "' .. newUrl .. '";'
  hs.osascript.javascript(script)
end

local function swapToDomain(domain, protocol)
  return function()
    local url = getChromeUrl()
    if not url then
      return
    end

    local newUrl = url
      :gsub("^https?://", protocol .. "://")
      :gsub("([^/]+)//([^/]+)", "%1//" .. domain)

    setChromeUrl(newUrl)
  end
end

-- Host-keyed URL swap hooks: each fn(url) returns false if it does not apply,
-- or a string (full replacement URL) if it does. For a given host, handlers
-- run in registration order; the first non-false return wins.
--
-- A private Hammerspoon snippet or corporate nix module can call
-- registerUrlSwapHandler without editing this file, e.g. after require:
--   registerUrlSwapHandler("app.internal.example", function(url) ... end)
local swapHandlersByHost = {}

function registerUrlSwapHandler(host, fn)
  if not swapHandlersByHost[host] then
    swapHandlersByHost[host] = {}
  end
  table.insert(swapHandlersByHost[host], fn)
end
local function hostFromUrl(url)
  return url:match("^https?://([^/:?#]+)") or ""
end

local function swapUrlWithRegisteredHandlers()
  local url = getChromeUrl()
  if not url then
    return
  end

  local host = hostFromUrl(url)
  local chain = swapHandlersByHost[host]
  if not chain then
    return
  end

  for _, fn in ipairs(chain) do
    local newUrl = fn(url)
    if newUrl ~= false and type(newUrl) == "string" then
      setChromeUrl(newUrl)
      return
    end
  end
end

-- app.graphite.com -> app.stg.graphite.com (one-way)
registerUrlSwapHandler("app.graphite.com", function(u)
  if
    u:match("app%.graphite%.com/") and not u:match("app%.stg%.graphite%.com/")
  then
    return u:gsub("app%.graphite%.com", "app.stg.graphite.com")
  end
  return false
end)

-- Graphite staging PR -> GitHub PR
registerUrlSwapHandler("app.stg.graphite.com", function(u)
  local org, repo, number =
    u:match("app%.stg%.graphite%.com/github/pr/([^/]+)/([^/]+)/(%d+)")
  if org then
    return "https://github.com/" .. org .. "/" .. repo .. "/pull/" .. number
  end
  return false
end)

-- GitHub PR -> Graphite (prod for anysphere/*, staging otherwise)
registerUrlSwapHandler("github.com", function(u)
  local org, repo, number = u:match("github%.com/([^/]+)/([^/]+)/pull/(%d+)")
  if not org then
    return false
  end

  local host = u:find("anysphere/", 1, true) and "app.graphite.com"
    or "app.stg.graphite.com"
  return "https://"
    .. host
    .. "/github/pr/"
    .. org
    .. "/"
    .. repo
    .. "/"
    .. number
end)

-- I use a super special keybind system for jerks
superKey
  :bind("1")
  :toFunction("Swap: localhost:3000", swapToDomain("localhost:3000", "https"))
superKey:bind("2"):toFunction(
  "Swap: app.stg.graphite.com",
  swapToDomain("app.stg.graphite.com", "https")
)

superKey
  :bind("3")
  :toFunction("Swap: GitHub <-> Graphite", swapUrlWithRegisteredHandlers)

-- But you can just use this for standard keybinding by uncommenting the
-- following lines & deleting the 2 lines above:
-- (edit your keybindings to taste)

-- hs.hotkey.bind({ 'cmd', 'alt', 'ctrl' }, '1', swapToDomain('localhost:3000'))
-- hs.hotkey.bind({ 'cmd', 'alt', 'ctrl' }, '2', swapToDomain('app.stg.graphite.dev'))
