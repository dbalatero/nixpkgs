{ config, lib, pkgs, ... }:

{
  programs.vscode = {
    enable = true;

    extensions = with pkgs.vscode-extensions; [
      asvetliakov.vscode-neovim
      bbenoist.nix
    ];

    userSettings = {
      "editor.fontFamily" = "'Inconsolata Go NerdFont Regular', Menlo, Monaco, 'Courier New', monospace";
      "terminal.external.linuxExec" = "xterm-256color";
      "terminal.integrated.experimentalRestore" = true;
      "terminal.integrated.fontFamily" = "InconsolataGo Nerd Font";
      "terminal.integrated.fontSize" = 14;
      "update.mode" = "none";
      "vscode-neovim.neovimInitPath" = "/Users/dbalatero/.config/nvim/vscode.vim";
      "window.nativeFullScreen" = false;
      "window.newWindowDimensions" = "maximized";
      "workbench.panel.defaultLocation" = "right";
      "update.channel" = "none";
      "security.workspace.trust.enabled" = true;
      "zenMode.fullScreen" = false;
      "workbench.statusBar.visible" = true;
      "workbench.colorTheme" = "One Dark Pro Mix";
      "breadcrumbs.enabled" = false;
      "editor.minimap.enabled" = false;
      "workbench.activityBar.visible" = false;
      "extensions.experimental.affinity" = {
        "asvetliakov.vscode-neovim" = 1;
      };
      "vscode-neovim.neovimExecutablePaths.darwin" = "/Users/dbalatero/.nix-profile/bin/nvim";
      "vscode-neovim.neovimInitVimPaths.darwin" = "/Users/dbalatero/.config/nvim/vscode.vim";
      "editor.accessibilitySupport" = "off";
      "vscode-neovim.neovimClean" = true;
      "workbench.startupEditor" = "none";
      "[javascript]" = {
        "editor.defaultFormatter" = "esbenp.prettier-vscode";
      };
      "editor.formatOnSave" = true;
      "editor.tabSize" = 2;
      "editor.detectIndentation" = false;
      "window.zoomLevel" = 3;
    };

    keybindings = [
      {
        command = "vscode-neovim.compositeEscape1";
        key = "j";
        when = "neovim.mode == insert";
        args = "j";
      }
      {
        command = "vscode-neovim.compositeEscape2";
        key = "k";
        when = "neovim.mode == insert";
        args = "k";
      }
      {
        key = "ctrl+h";
        command = "workbench.action.navigateLeft";
      }
      {
        key = "ctrl+l";
        command = "workbench.action.navigateRight";
      }
      {
        key = "ctrl+k";
        command = "workbench.action.navigateUp";
      }
      {
        key = "ctrl+j";
        command = "workbench.action.navigateDown";
      }
      {
        key = "ctrl+p";
        command = "workbench.action.quickOpen";
      }
      {
        key = "alt+left";
        command = "workbench.action.terminal.resizePaneLeft";
        when = "terminalFocus";
      }
      {
        key = "alt+right";
        command = "workbench.action.terminal.resizePaneRight";
        when = "terminalFocus";
      }
      {
        key = "ctrl+t";
        command = "workbench.action.terminal.toggleTerminal";
      }
      {
        key = "ctrl+a t";
        command = "pay.cmd.test.currentLine";
      }
      {
        key = "ctrl+a s";
        command = "pay.cmd.test.activeEditor";
      }
    ];
  };
}
