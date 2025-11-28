{ config, lib, pkgs, ... }: let
  brewPath = "${config.homebrew.brewPrefix}/brew";
in {
  nix.enable = false;

  # Primary user for system defaults
  system.primaryUser = "dbalatero";

  system.defaults = {
    dock.autohide = true;
    finder.AppleShowAllExtensions = true;
    NSGlobalDomain.AppleShowAllExtensions = true;
  };

  # Enable sudo with Touch ID
  security.pam.services.sudo_local.touchIdAuth = true;

  # Homebrew configuration
  system.activationScripts.ensureHomebrew.text = ''
    echo >&2 "ensuring Homebrew is available..."
    if [ ! -x '${brewPath}' ]; then
      NONINTERACTIVE=1 sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
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

  homebrew = {
    enable = true;
    onActivation.cleanup = "zap";

    casks = [
      "ghostty"
    ];
  };

  # Necessary for using flakes on this system
  nix.settings.experimental-features = "nix-command flakes";

  # Set Git commit hash for darwin-version
  system.configurationRevision = null;

  # Used for backwards compatibility
  system.stateVersion = 5;
}