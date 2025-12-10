{pkgs, ...}: {
  home.packages = with pkgs; [
    blueutil
    m1ddc

    (writeShellScriptBin "daily" (builtins.readFile ./bin/daily.sh))
    (writeShellScriptBin "dnd-toggle" (builtins.readFile ./bin/dnd-toggle.sh))
  ];

  home.file.".hammerspoon" = {
    enable = true;
    recursive = true;
    source = ./config;
  };

  home.file.".hammerspoon/Spoons/SpoonInstall.spoon" = {
    source = pkgs.fetchzip {
      url = "https://github.com/Hammerspoon/Spoons/raw/30b4f6013d48bd000a8ddecff23e5a8cce40c73c/Spoons/SpoonInstall.spoon.zip";
      hash = "sha256-3f0d4znNuwZPyqKHbZZDlZ3gsuaiobhHPsefGIcpCSE=";
    };
  };

  home.file.".hammerspoon/Spoons/HyperKey.spoon".source = pkgs.fetchFromGitHub {
    owner = "dbalatero";
    repo = "HyperKey.spoon";
    rev = "93438b908f98f6cdef151439a25bed7245e0462f";
    hash = "sha256-MJONyfDk8qDhoqJ1kjXW9uoY6ac5tRVimjwx3+pIpho=";
  };

  home.file.".hammerspoon/Spoons/VimMode.spoon".source = pkgs.fetchFromGitHub {
    owner = "dbalatero";
    repo = "VimMode.spoon";
    rev = "dda997f79e240a2aebf1929ef7213a1e9db08e97";
    hash = "sha256-zpx2lh/QsmjP97CBsunYwJslFJOb0cr4ng8YemN5F0Y=";
  };

  home.file.".hammerspoon/Spoons/SkyRocket.spoon".source = pkgs.fetchFromGitHub {
    owner = "dbalatero";
    repo = "SkyRocket.spoon";
    rev = "9f469623773f0f3a6f28c316eb4253f2ac659d2a";
    hash = "sha256-U74TD1Q1Rozf9SxtwEr8xcmURm/pmlJknAz3WadtMdI=";
  };
}
