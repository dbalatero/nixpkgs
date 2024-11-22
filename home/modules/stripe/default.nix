{
  imports = [
    ./neovim
    ./zsh.nix
  ];

  programs.git.userEmail = "dbalatero@stripe.com";

  programs.zsh = {
    initExtra = ''
      export PATH="$PATH:$HOME/stripe/work/exe"
    '';

    shellAliases = {
      b = "work begin";
      p = "work pr show";
      r = "work review";
      st = "~/stripe/st/bin/repo-dev";
    };
  };
}
