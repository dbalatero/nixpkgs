{
  programs.alacritty = {
    enable = true;

    settings = {
      live_config_reload = true;
      working_directory = "None";

      bell.duration = 0;
      colors.draw_bold_text_with_bright_colors = true;

      cursor = {
        style = "Block";
        unfocused_hollow = true;
      };

      env = {
        TERM = "xterm-256color";
      };

      mouse = {
        hide_when_typing = true;
      };

      scrolling = {
        history = 10000;
        multiplier = 3;
      };

      window = {
        decorations = "none";
        dynamic_title = false;
        opacity = 1.0;
        startup_mode = "SimpleFullscreen";
        title = "Alacritty";

        padding = {
          x = 0;
          y = 0;
        };
      };

      keyboard.bindings = [
        {
          chars = "\\u001Ba";
          key = "A";
          mods = "Alt";
        }
        {
          chars = "\\u001Bb";
          key = "B";
          mods = "Alt";
        }
        {
          chars = "\\u001Bc";
          key = "C";
          mods = "Alt";
        }
        {
          chars = "\\u001Bd";
          key = "D";
          mods = "Alt";
        }
        {
          chars = "\\u001Be";
          key = "E";
          mods = "Alt";
        }
        {
          chars = "\\u001Bf";
          key = "F";
          mods = "Alt";
        }
        {
          chars = "\\u001Bg";
          key = "G";
          mods = "Alt";
        }
        {
          chars = "\\u001Bh";
          key = "H";
          mods = "Alt";
        }
        {
          chars = "\\u001Bi";
          key = "I";
          mods = "Alt";
        }
        {
          chars = "\\u001Bj";
          key = "J";
          mods = "Alt";
        }
        {
          chars = "\\u001Bk";
          key = "K";
          mods = "Alt";
        }
        {
          chars = "\\u001Bl";
          key = "L";
          mods = "Alt";
        }
        {
          chars = "\\u001Bm";
          key = "M";
          mods = "Alt";
        }
        {
          chars = "\\u001Bn";
          key = "N";
          mods = "Alt";
        }
        {
          chars = "\\u001Bo";
          key = "O";
          mods = "Alt";
        }
        {
          chars = "\\u001Bp";
          key = "P";
          mods = "Alt";
        }
        {
          chars = "\\u001Bq";
          key = "Q";
          mods = "Alt";
        }
        {
          chars = "\\u001Br";
          key = "R";
          mods = "Alt";
        }
        {
          chars = "\\u001Bs";
          key = "S";
          mods = "Alt";
        }
        {
          chars = "\\u001Bt";
          key = "T";
          mods = "Alt";
        }
        {
          chars = "\\u001Bu";
          key = "U";
          mods = "Alt";
        }
        {
          chars = "\\u001Bv";
          key = "V";
          mods = "Alt";
        }
        {
          chars = "\\u001Bw";
          key = "W";
          mods = "Alt";
        }
        {
          chars = "\\u001Bx";
          key = "X";
          mods = "Alt";
        }
        {
          chars = "\\u001By";
          key = "Y";
          mods = "Alt";
        }
        {
          chars = "\\u001Bz";
          key = "Z";
          mods = "Alt";
        }
        {
          chars = "\\u001BA";
          key = "A";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BB";
          key = "B";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BC";
          key = "C";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BD";
          key = "D";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BE";
          key = "E";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BF";
          key = "F";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BG";
          key = "G";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BH";
          key = "H";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BI";
          key = "I";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BJ";
          key = "J";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BK";
          key = "K";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BL";
          key = "L";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BM";
          key = "M";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BN";
          key = "N";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BO";
          key = "O";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BP";
          key = "P";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BQ";
          key = "Q";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BR";
          key = "R";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BS";
          key = "S";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BT";
          key = "T";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BU";
          key = "U";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BV";
          key = "V";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BW";
          key = "W";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BX";
          key = "X";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BY";
          key = "Y";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001BZ";
          key = "Z";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B1";
          key = "Key1";
          mods = "Alt";
        }
        {
          chars = "\\u001B2";
          key = "Key2";
          mods = "Alt";
        }
        {
          chars = "\\u001B3";
          key = "Key3";
          mods = "Alt";
        }
        {
          chars = "\\u001B4";
          key = "Key4";
          mods = "Alt";
        }
        {
          chars = "\\u001B5";
          key = "Key5";
          mods = "Alt";
        }
        {
          chars = "\\u001B6";
          key = "Key6";
          mods = "Alt";
        }
        {
          chars = "\\u001B7";
          key = "Key7";
          mods = "Alt";
        }
        {
          chars = "\\u001B8";
          key = "Key8";
          mods = "Alt";
        }
        {
          chars = "\\u001B9";
          key = "Key9";
          mods = "Alt";
        }
        {
          chars = "\\u001B0";
          key = "Key0";
          mods = "Alt";
        }
        {
          chars = "\\u0000";
          key = "Space";
          mods = "Control";
        }
        {
          chars = "\\u001B`";
          key = "`";
          mods = "Alt";
        }
        {
          chars = "\\u001B~";
          key = "`";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B.";
          key = "Period";
          mods = "Alt";
        }
        {
          chars = "\\u001B*";
          key = "Key8";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B#";
          key = "Key3";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B>";
          key = "Period";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B<";
          key = "Comma";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B_";
          key = "Minus";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B%";
          key = "Key5";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B^";
          key = "Key6";
          mods = "Alt|Shift";
        }
        {
          chars = "\\u001B\\\\";
          key = "Backslash";
          mods = "Alt";
        }
        {
          chars = "\\u001B|";
          key = "Backslash";
          mods = "Alt|Shift";
        }
        {
          action = "ToggleSimpleFullscreen";
          key = "Return";
          mods = "Command";
        }
        {
          action = "IncreaseFontSize";
          key = "Plus";
          mods = "Command";
        }
        {
          action = "DecreaseFontSize";
          key = "Minus";
          mods = "Command";
        }
        {
          action = "ResetFontSize";
          key = "Key0";
          mods = "Command";
        }
        {
          action = "Paste";
          key = "V";
          mods = "Command";
        }
        {
          action = "Copy";
          key = "C";
          mods = "Command";
        }
        {
          action = "Hide";
          key = "H";
          mods = "Command";
        }
        {
          action = "Quit";
          key = "Q";
          mods = "Command";
        }
      ];
    };
  };
}
