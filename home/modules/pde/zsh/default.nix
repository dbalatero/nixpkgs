{
  config,
  lib,
  pkgs,
  ...
}: {
  home.packages = with pkgs; [
    fasd
    fd
    neofetch
    ripgrep
    zsh
  ];

  programs.direnv.enable = true;
  programs.eza.enable = true;
  programs.fzf = {
    enable = true;
    defaultCommand = "rg --files --hidden --glob '!{node_modules/*,.git/*}'";
    fileWidgetCommand = "rg --files --hidden --glob '!{node_modules/*,.git/*}'";
  };

  programs.starship = {
    enable = true;
    enableZshIntegration = true;
    settings = {
      # Minimal prompt for speed
      format = lib.concatStrings [
        "$hostname"
        "$directory"
        "$git_branch"
        "$line_break"
        "$character"
      ];

      # Show hostname
      hostname = {
        ssh_only = true;
        format = "[$hostname]($style) ";
        style = "bold green";
      };

      # Show only directory
      directory = {
        truncation_length = 3;
        truncate_to_repo = true;
      };

      # Show only git branch name, nothing else
      git_branch = {
        format = "[$symbol$branch]($style) ";
        symbol = "";
        style = "bold purple";
      };

      # Disable git status entirely for speed
      git_status.disabled = true;

      # Disable all other modules for maximum speed
      aws.disabled = true;
      gcloud.disabled = true;
      nodejs.disabled = true;
      ruby.disabled = true;
      python.disabled = true;
      rust.disabled = true;
      golang.disabled = true;
      docker_context.disabled = true;
      package.disabled = true;
    };
  };

  home.file.".zsh/secrets" = {
    recursive = true;
    source = ./secrets;
  };

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
        {name = "dbalatero/fzf-git";}
        {name = "wookayin/fzf-fasd";}
        {name = "dbalatero/fast-syntax-highlighting";}
        {name = "hlissner/zsh-autopair";}
        {name = "chriskempson/base16-shell";}
        {name = "MichaelAquilina/zsh-you-should-use";}
      ];
    };

    sessionVariables = {
      # Editor
      EDITOR = "nvim";
      NVIM_TUI_ENABLE_TRUE_COLOR = "1";

      # Tmux UTF8 support
      LANG = "en_US.UTF-8";
      LC_CTYPE = "en_US.UTF-8";

      # Fix GPG's bullshit
      GPG_TTY = "$(tty)";

      HOMEBREW_NO_AUTO_UPDATE = "1";

      # Restic/Backblaze
      # restic mount -r $SYNC_REPO ~/backblaze
      RESTIC_REPOSITORY = "b2:dbalatero-backup";
      SYNC_REPO = "$RESTIC_REPOSITORY:/Sync";
      FREEZE_REPO = "$RESTIC_REPOSITORY:/Freeze";

      PATH = "./node_modules/.bin:$HOME/.config/base16-shell:$PATH";
      TERM = "xterm-256color";
    };

    # zshenv
    envExtra = ''
      export XDG_CONFIG_HOME="$HOME/.config"
      export XDG_DATA_HOME="$HOME/.local/share"
    '';

    shellAliases = {
      "6" = "exec zsh";
      j = "z"; # autojump style for fasd
      l = "ls -al";
      p = "gt pr";

      tk = "tmux kill-session";
      tn = "tmuxinator";
      vim = "nvim";

      weather = "curl wttr.in";

      switch = "cd ~/.config/nixpkgs && git pull origin main && ./bin/switch && cd -";
      dev = "tn start remote";
    };

    initContent = lib.mkMerge [
      (lib.mkBefore ''
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
      '')
      ''
        # hooks
        eval "$(fasd --init auto)"

        # Print theme colors
        function theme_colors() {
          for code ({000..255}) print -P -- \
            "$code: %F{$code}This is how your text would look like%f"
        }

        # Use jk to exit insert mode on the command line
        bindkey -M viins 'jk' vi-cmd-mode

        # Set vi mode AGAIN
        bindkey -v

        if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
          . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
        fi

        if [ -f "$HOME/.cargo/env" ]; then
          source "$HOME/.cargo/env"
        fi

        for file in $HOME/.zsh/secrets/**/*.zsh
        do
          source $file
        done

        if [ -f "$HOME/.zsh.experimental" ]; then
          source "$HOME/.zsh.experimental"
        fi
      ''
    ];
  };
}
