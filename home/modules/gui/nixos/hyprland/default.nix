{
  config,
  lib,
  pkgs,
  ...
}: {
  # Install audio control tools
  home.packages = with pkgs; [
    pwvucontrol  # Modern PipeWire volume control GUI
    wireplumber  # Includes wpctl for CLI control
  ];

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

      # Input settings - keyboard repeat rate and caps lock as control
      input = {
        kb_options = "ctrl:nocaps";
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

        # Audio control - open GUI mixer
        "$mainMod, A, exec, pwvucontrol"
      ];

      # Volume and audio device control
      bindl = [
        # Volume control
        ", XF86AudioRaiseVolume, exec, wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+"
        ", XF86AudioLowerVolume, exec, wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"
        ", XF86AudioMute, exec, wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"
        ", XF86AudioMicMute, exec, wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"
      ];
    };
  };
}
