{ config, lib, pkgs, ... }:

{
  home.packages = with pkgs; [
    fasd
    fd
    fzf
    neofetch
    nodenv
    gitstatus
    zsh
  ];

  programs.direnv.enable = true;
  programs.eza.enable = true;
  programs.fzf = {
    enable = true;
    defaultCommand = "rg --files --hidden --glob '!{node_modules/*,.git/*}'";
    fileWidgetCommand = "rg --files --hidden --glob '!{node_modules/*,.git/*}'";
  };
  programs.pyenv.enable = true;
  programs.rbenv.enable = true;

  programs.starship.enable = true;
  xdg.configFile."starship.toml".source = ./starship.toml;

  programs.zsh = {
    enable = true;
    enableCompletion = true;

    defaultKeymap = "viins"; # vi mode
    syntaxHighlighting.enable = true;

    history = {
      size = 10000;
      save = 10000;
      extended = true;
      share = true;
      path = "${config.xdg.dataHome}/zsh/history";
    };

    oh-my-zsh = {
      enable = true;
      plugins = [
        "git"
      ];
    };

    zplug = {
      enable = true;
      plugins = [
        { name = "dbalatero/fzf-git"; }
        { name = "wookayin/fzf-fasd"; }
        { name = "twang817/zsh-ssh-agent"; }
        { name = "dbalatero/fast-syntax-highlighting"; }
        { name = "hlissner/zsh-autopair"; }
      ];
    };

    sessionVariables = {
      # Editor
      EDITOR = "nvim";
      NVIM_TUI_ENABLE_TRUE_COLOR = "1";

      # Tmux UTF8 support
      LANG = "en_US.UTF-8";
      LC_CTYPE= "en_US.UTF-8";

      # Fix GPG's bullshit
      GPG_TTY = "$(tty)";

      HOMEBREW_NO_AUTO_UPDATE = "1";
      GITSTATUS_DAEMON = "$HOME/.nix-profile/bin/gitstatusd";
    };

    shellAliases = {
      "6" = "exec zsh";
      j = "z"; # autojump style for fasd
      l = "ls -al";

      tk = "tmux kill-session";
      tn = "tmuxinator";
      # vim = "nvim";

      weather = "curl wttr.in";
    };

    initExtraFirst = ''
# Disable auto title so tmux window titles don't get messed up.
export DISABLE_AUTO_TITLE="true"

# Maintain a stack of cd directory traversals for `popd`
setopt AUTO_PUSHD

# Allow extended matchers like ^file, etc
set -o EXTENDED_GLOB

# ========= History settings =========

setopt append_history
setopt hist_expire_dups_first
setopt hist_ignore_dups
setopt hist_ignore_space
setopt inc_append_history
setopt extended_glob
    '';

    initExtra = ''
# hooks
eval "$(fasd --init auto)"
eval "$(nodenv init -)"

# Print theme colors
function theme_colors() {
  for code ({000..255}) print -P -- \
    "$code: %F{$code}This is how your text would look like%f"
}

# Use jk to exit insert mode on the command line
bindkey -M viins 'jk' vi-cmd-mode

if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
  . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
fi


    '';
  };
}
