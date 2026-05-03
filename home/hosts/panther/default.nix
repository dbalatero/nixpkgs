{...}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui/terminal
    ../../modules/gui/nixos
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";

  programs.plasma.workspace.wallpaper = "${./wallpaper.jpg}";

  programs.ghostty.settings = {
    font-size = 14;
  };
}
