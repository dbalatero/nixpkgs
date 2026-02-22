{pkgs, ...}: {
  programs.nixvim = {
    plugins = {
      tmux-navigator.enable = true;
    };

    extraPlugins = (
      map pkgs.vimUtils.buildVimPlugin [
        {
          name = "better-vim-tmux-resizer";
          src = pkgs.fetchFromGitHub {
            owner = "RyanMillerC";
            repo = "better-vim-tmux-resizer";
            rev = "a791fe5b4433ac43a4dad921e94b7b5f88751048";
            hash = "sha256-1uHcQQUnViktDBZt+aytlBF1ZG+/Ifv5VVoKSyM9ML0=";
          };
        }
      ]
    );

    opts = {
      # set our shell to be bash for fast tmux switching times
      # see: https://github.com/christoomey/vim-tmux-navigator/issues/72
      shell = "${pkgs.bash}/bin/bash --norc";
    };
  };
}
