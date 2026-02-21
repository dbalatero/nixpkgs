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

local function swapGithubGraphite()
  local url = getChromeUrl()
  if not url then
    return
  end

  local newUrl = nil

  -- Graphite -> GitHub
  local org, repo, number = url:match("app%.stg%.graphite%.com/github/pr/([^/]+)/([^/]+)/(%d+)")
  if org then
    newUrl = "https://github.com/" .. org .. "/" .. repo .. "/pull/" .. number
  end

  -- GitHub -> Graphite
  if not newUrl then
    org, repo, number = url:match("github%.com/([^/]+)/([^/]+)/pull/(%d+)")
    if org then
      newUrl = "https://app.stg.graphite.com/github/pr/" .. org .. "/" .. repo .. "/" .. number
    end
  end

  if not newUrl then
    return
  end

  setChromeUrl(newUrl)
end

-- I use a super special keybind system for jerks
superKey
  :bind("1")
  :toFunction("Swap: localhost:3000", swapToDomain("localhost:3000", "https"))
superKey:bind("2"):toFunction(
  "Swap: app.stg.graphite.com",
  swapToDomain("app.stg.graphite.com", "https")
)

superKey:bind("3"):toFunction(
  "Swap: GitHub <-> Graphite",
  swapGithubGraphite
)

-- But you can just use this for standard keybinding by uncommenting the
-- following lines & deleting the 2 lines above:
-- (edit your keybindings to taste)

-- hs.hotkey.bind({ 'cmd', 'alt', 'ctrl' }, '1', swapToDomain('localhost:3000'))
-- hs.hotkey.bind({ 'cmd', 'alt', 'ctrl' }, '2', swapToDomain('app.stg.graphite.dev'))
