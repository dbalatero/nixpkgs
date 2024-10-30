{pkgs, ...}: let
  tmux-suspend = pkgs.tmuxPlugins.mkTmuxPlugin {
    pluginName = "tmux-suspend";
    version = "097f09dabd64084ab0c72ae75df4b5a89bb431a6";
    rtpFilePath = "suspend.tmux";
    src = pkgs.fetchFromGitHub {
      owner = "MunifTanjim";
      repo = "tmux-suspend";
      rev = "1a2f806666e0bfed37535372279fa00d27d50d14";
      sha256 = "sha256-+1fKkwDmr5iqro0XeL8gkjOGGB/YHBD25NG+w3iW+0g=";
    };
  };
in {
  imports = [
    ./modules/common.nix
    ./modules/darwin
    ./modules/stripe
  ];

  home.homeDirectory = "/Users/dbalatero";
  home.username = "dbalatero";

  programs.tmux.plugins = [
    {
      # We need nested tmux on stripe laptops
      plugin = tmux-suspend;
    }
  ];
}
