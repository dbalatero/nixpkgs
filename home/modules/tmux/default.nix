{ config, lib, pkgs, ... }:

let
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
in
{
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
        plugin = tmuxPlugins.prefix-highlight;
        extraConfig = ''
          set -g @prefix_highlight_bg 'colour33'
          set -g @prefix_highlight_show_copy_mode 'on'
          set -g @prefix_highlight_copy_mode_attr 'fg=colour234,bg=yellow,bold'
        '';
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

          # Resize panes with meta+hjkl
          bind -n M-h if-shell "$is_vim_emacs" "send-keys M-h" "resize-pane -L 10"
          bind -n M-l if-shell "$is_vim_emacs" "send-keys M-l" "resize-pane -R 10"
          bind -n M-k if-shell "$is_vim_emacs" "send-keys M-k" "resize-pane -U 5"
          bind -n M-j if-shell "$is_vim_emacs" "send-keys M-j" "resize-pane -D 5"
        '';
      }
    ];

    extraConfig = (builtins.concatStringsSep "\n\n" [
      (builtins.readFile ./tmux.conf)
      (builtins.readFile ./tmux.theme.conf)
    ]);
  };
}

# TODO: macos only
# enable system copy/paste:
# https://github.com/ChrisJohnsen/tmux-MacOSX-pasteboard
# ------
#   set-option -g default-command "reattach-to-user-namespace -l zsh"
#
# ------and "Copy mode":
#
#   unbind p
#   bind p paste-buffer
#   bind -T copy-mode-vi 'v' send -X begin-selection
#   bind -T copy-mode-vi 'r' send -X rectangle-toggle
#   bind -T copy-mode-vi 'y' send -X copy-pipe "reattach-to-user-namespace pbcopy"
#   unbind -T copy-mode-vi Enter
#   bind-key -T copy-mode-vi Enter send -X copy-pipe "reattach-to-user-namespace pbcopy"
#
# ------ and clipboard
#
# bind C-c run "tmux save-buffer - | reattach-to-user-namespace pbcopy"
# bind C-v run "reattach-to-user-namespace pbpaste | tmux load-buffer - && tmux paste-buffer"

