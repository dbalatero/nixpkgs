{pkgs, ...}: {
  home.packages = with pkgs; [
    fd
    gcc  # C/C++ compiler (provides gcc, g++, cc)
    readline
    ripgrep
    wget
    xz
  ];
}
