{pkgs, ...}: {
  home.packages = with pkgs; [
    coreutils
    fd
    readline
    ripgrep
    wget
    xz
  ];
}
