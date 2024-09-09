{pkgs, ...}: {
  home.packages = with pkgs; [
    # Installs to:
    #  ~/.nix-profile/share/fonts/truetype/NerdFonts
    (nerdfonts.override {
      fonts = [
        "FiraCode"
        "JetBrainsMono"
        "InconsolataGo"
      ];
    })
  ];
}
