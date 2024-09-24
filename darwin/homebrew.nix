{ config, lib, pkgs, ... }:
let
  brewPath = "${config.homebrew.brewPrefix}/brew";
  isStripe = config.networking.hostName == "st-dbalatero1";

  extraPackages = if isStripe then [] else [
    "google-chrome"
  ];
in
{
  # From: https://github.com/robhanlon22/dotfiles/blob/main/nix-darwin/homebrew.nix
  system.activationScripts.preUserActivation.text = ''
    echo >&2 "ensuring Homebrew is available..."
    if [ ! -x '${brewPath}' ]; then
      NONINTERACTIVE=1 bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
  '';

  programs.zsh.interactiveShellInit = ''
    eval "$('${brewPath}' shellenv)"
    export PATH="${lib.makeBinPath (config.environment.profiles ++ ["$PATH"])}"
    typeset -aU path
    path=(''${path[@]})
    export HOMEBREW_NO_ENV_HINTS=1
    source '${pkgs.oh-my-zsh}/share/oh-my-zsh/plugins/brew/brew.plugin.zsh'
  '';

  launchd.user.agents.brew-upgrade = {
    script = ''
      '${brewPath}' upgrade --greedy && '${brewPath}' cleanup && '${brewPath}' autoremove
    '';
    serviceConfig.StartCalendarInterval = [
      {
        Hour = 9;
        Minute = 0;
      }
    ];
  };

  homebrew = {
    enable = true;
    brews = [];
    casks = [
      "alfred"
      "bartender"
      "firefox"
      "hammerspoon"
      "karabiner-elements"
      "monitorcontrol"
      "spotify"
      "vlc"
    ] ++ extraPackages;
  };
}
