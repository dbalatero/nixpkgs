{pkgs, ...}: {
  home.packages = with pkgs; [
    fd
    readline
    ripgrep
    wget
    xz
  ];
}
