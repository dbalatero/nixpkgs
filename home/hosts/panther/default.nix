{pkgs, ...}: {
  imports = [
    ../../modules/default.nix
    ../../modules/gui/terminal
    ../../modules/gui/nixos
  ];

  home.homeDirectory = "/home/dbalatero";
  home.username = "dbalatero";

  home.packages = with pkgs; [
    abcde
    cddiscid
    cdparanoia
    flac
  ];

  home.file.".abcde.conf".text =
    builtins.concatStringsSep "\n" [
      "CDDBMETHOD=musicbrainz"
      "CDROM=/dev/sr0"
      "CDROMREADERSYNTAX=cdparanoia"
      "OUTPUTTYPE=flac"
      "FLACENCODERSYNTAX=flac"
      "FLACOPTS=\"--best --silent\""
      "ACTIONS=cddb,read,encode,tag,move,clean"
      "PADTRACKS=y"
      "MAXPROCS=4"
      "OUTPUTFORMAT='\${ARTISTFILE}/\${ALBUMFILE}/\${TRACKNUM} - \${TRACKFILE}'"
      "VAOUTPUTFORMAT='Various Artists/\${ALBUMFILE}/\${TRACKNUM} - \${ARTISTFILE} - \${TRACKFILE}'"
      ""
    ];

  programs.plasma.workspace.wallpaper = "${./wallpaper.jpg}";

  programs.ghostty.settings = {
    font-size = 14;
  };
}
