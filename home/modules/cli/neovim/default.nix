{pkgs, ...}: {
  programs.nixvim = {
    enable = true;

    # Basic options
    opts = {
      number = true;
      relativenumber = true;
      shiftwidth = 2;
      tabstop = 2;
      expandtab = true;
    };
  };
}
