{pkgs, ...}: {
  home.packages = with pkgs; [
    restic
  ];
}
