{ config, lib, pkgs, ... }:

let
  pyenvRootDirectory = "${config.xdg.dataHome}/pyenv";
in
{
  programs.pyenv = {
    enable = true;
    rootDirectory = pyenvRootDirectory;
  };

  programs.zsh.initExtra = ''
    export PYENV_ROOT="${pyenvRootDirectory}"
    eval "$(${pkgs.pyenv}/bin/pyenv virtualenv-init -)"
  '';

  home.file."${config.xdg.dataHome}/pyenv/plugins" = {
    source = pkgs.linkFarm "pyenv-plugins" [
      {
        name = "pyenv-virtualenv";
        path = pkgs.fetchFromGitHub {
          owner = "pyenv";
          repo = "pyenv-virtualenv";
          rev = "v1.2.4";
          hash = "sha256-NgtowwE1T5NoiYiL18vdpYumVuPSWoDCOyP2//d+uHk=";
        };
      }
    ];
  };
}
