{
  config,
  lib,
  pkgs,
  ...
}: let
  tmux-pain-control = pkgs.tmuxPlugins.mkTmuxPlugin {
    pluginName = "tmux-pain-control";
    version = "097f09dabd64084ab0c72ae75df4b5a89bb431a6";
    src = pkgs.fetchFromGitHub {
      owner = "dbalatero";
      repo = "tmux-pain-control";
      rev = "097f09dabd64084ab0c72ae75df4b5a89bb431a6";
      sha256 = "sha256-oMwLMG6ZRdVz4qxTC9H4NsGkQyDnoJkMzchdHQDGgHQ=";
    };
  };

  tmux-prefix-highlight = pkgs.tmuxPlugins.mkTmuxPlugin {
    pluginName = "tmux-prefix-highlight";
    version = "489a96189778a21d2f5f4dbbbc0ad2cec8f6c854";
    rtpFilePath = "prefix_highlight.tmux";
    src = pkgs.fetchFromGitHub {
      owner = "tmux-plugins";
      repo = "tmux-prefix-highlight";
      rev = "489a96189778a21d2f5f4dbbbc0ad2cec8f6c854";
      sha256 = "sha256-GXqlwl1TPgXX1Je/ORjGFwfCyz17ZgdsoyOK1P3XF18=";
    };
  };
in {
  xdg.configFile."tmux/tmux.theme.conf".source = ./tmux.theme.conf;

  programs.tmux = {
    enable = true;
    tmuxinator.enable = true;

    aggressiveResize = true;
    baseIndex = 1;
    historyLimit = 50000;
    keyMode = "vi";
    mouse = true;
    prefix = lib.mkDefault "C-o";
    shell = "${config.home.homeDirectory}/.nix-profile/bin/zsh";
    terminal = "xterm-256color";

    plugins = with pkgs; [
      tmuxPlugins.battery
      tmuxPlugins.better-mouse-mode
      tmuxPlugins.copycat
      tmuxPlugins.open
      {
        plugin = tmuxPlugins.yank;
        extraConfig = "set -g set-clipboard on";
      }
      {
        plugin = tmux-pain-control;
        extraConfig = ''
          set-env -g @pane_resize "20"

          # Smart pane switching with awareness of vim splits
          is_vim_emacs='echo "#{pane_current_command}" | \
              grep -iqE "((^|\/)g?(view|n?vim?x?)(diff)?$)|emacs"'

          # Move panes with ctrl+hjkl
          bind -n 'C-h' if-shell "$is_vim_emacs" "send-keys C-h" "select-pane -L"
          bind -n 'C-j' if-shell "$is_vim_emacs" "send-keys C-j" "select-pane -D"
          bind -n 'C-k' if-shell "$is_vim_emacs" "send-keys C-k" "select-pane -U"
          bind -n 'C-l' if-shell "$is_vim_emacs" "send-keys C-l" "select-pane -R"

          # enable in copy mode key table
          bind -Tcopy-mode-vi 'C-h' if-shell "$is_vim_emacs" "send-keys C-h" "select-pane -L"
          bind -Tcopy-mode-vi 'C-j' if-shell "$is_vim_emacs" "send-keys C-j" "select-pane -D"
          bind -Tcopy-mode-vi 'C-k' if-shell "$is_vim_emacs" "send-keys C-k" "select-pane -U"
          bind -Tcopy-mode-vi 'C-l' if-shell "$is_vim_emacs" "send-keys C-l" "select-pane -R"
          bind -Tcopy-mode-vi 'C-\' if-shell "$is_vim_emacs" "send-keys C-\\\\" "select-pane -l"

          # TODO: replace this with the better-vim-tmux-resizer plugin
          # Resize panes with meta+hjkl
          bind -n M-h if-shell "$is_vim_emacs" "send-keys M-h" "resize-pane -L 10"
          bind -n M-l if-shell "$is_vim_emacs" "send-keys M-l" "resize-pane -R 10"
          bind -n M-k if-shell "$is_vim_emacs" "send-keys M-k" "resize-pane -U 5"
          bind -n M-j if-shell "$is_vim_emacs" "send-keys M-j" "resize-pane -D 5"
        '';
      }
      {
        plugin = tmux-prefix-highlight;
        extraConfig = ''
          set -g @prefix_highlight_bg 'colour33'
          set -g @prefix_highlight_show_copy_mode 'on'
          set -g @prefix_highlight_copy_mode_attr 'fg=colour234,bg=yellow,bold'

          source ${config.xdg.configHome}/tmux/tmux.theme.conf;
        '';
      }
    ];

    extraConfig = builtins.concatStringsSep "\n\n" [
      (builtins.readFile ./tmux.conf)
    ];
  };
}
