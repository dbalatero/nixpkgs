{pkgs, ...}: {
  imports = [
    ./audio
    ./backups
    ./ghostty
  ];

  home.packages = with pkgs; [
    imagemagick
    (writeShellScriptBin "emoji-intensifies" (builtins.readFile ./bin/emoji-intensifies.sh))
  ];
}
