{ config, lib, pkgs, pkgsUnstable, ... }:

{
  home.packages = with pkgs; [
    fasd
    fd
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
    package = pkgsUnstable.fzf;
  };
  programs.pyenv.enable = true;

  programs.starship.enable = true;
  xdg.configFile."starship.toml".source = ./starship.toml;

  home.file.".zsh/secrets" = {
    recursive = true;
    source = ./secrets;
  };

  home.file.".base16_theme".source = ./themes/oceanic-next.sh;

  home.file.".inputrc".text = ''
set editing-mode vi
set keymap vi-command
  '';

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
        { name = "chriskempson/base16-shell"; }
      ];
    };

    # TODO figure out how these load!
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

      # Restic/Backblaze
      # restic mount -r $SYNC_REPO ~/backblaze
      RESTIC_REPOSITORY = "b2:dbalatero-backup";
      SYNC_REPO = "$RESTIC_REPOSITORY:/Sync";
      FREEZE_REPO = "$RESTIC_REPOSITORY:/Freeze";

      PATH = "./node_modules/.bin:$HOME/.config/base16-shell:$PATH";
    };

    shellAliases = {
      "6" = "exec zsh";
      j = "z"; # autojump style for fasd
      l = "ls -al";

      tk = "tmux kill-session";
      tn = "tmuxinator";
      vim = "nvim";

      weather = "curl wttr.in";
    };

    initExtraFirst = ''
[ -e "~/.zshenv" ] && source ~/.zshenv

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

for file in $HOME/.zsh/secrets/**/*.zsh
do
  source $file
done

[ -f ~/.base16_theme ] && source ~/.base16_theme
    '';
  };
}
