{
  config,
  lib,
  pkgs,
  ...
}: {
  wayland.windowManager.hyprland = {
    enable = true;
    xwayland.enable = true;

    settings = {
      # Program variables
      "$terminal" = "ghostty";
      "$fileManager" = "dolphin";
      "$menu" = "wofi --show drun";
      "$mainMod" = "SUPER";

      # Autostart
      exec-once = [
        "waybar"
      ];

      # Input settings - keyboard repeat rate
      input = {
        repeat_delay = 200;
        repeat_rate = 33;
      };

      # Custom keybindings
      bind = [
        "$mainMod, Q, exec, ghostty"
        "$mainMod, C, killactive"
        "$mainMod, M, exit"
        "$mainMod, D, exec, wofi --show drun"
        "$mainMod, E, exec, firefox"
      ];
    };
  };
}
