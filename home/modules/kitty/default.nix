{
  xdg.configFile."kitty/images/gradient_background.png" = {
    source = ./images/gradient_background.png;
  };

  programs.kitty = {
    enable = true;

    darwinLaunchOptions = ["--start-as=fullscreen"];

    keybindings = {
      "cmd+enter" = "toggle_fullscreen";
    };

    settings = {
      cursor_blink_interval = 0;
      cursor_shape = "block";

      enable_audio_bell = false;
      visual_bell_duration = 0;
      visual_bell_color = "none";
      window_alert_on_bell = false;

      remember_window_size = true;
      window_padding_width = 0;
      placement_strategy = "top-left";

      macos_hide_from_tasks = false;
      macos_option_as_alt = true;
      macos_hide_titlebar = true;
      macos_titlebar_color = "system";
      macos_traditional_fullscreen = true;
    };
  };
}
