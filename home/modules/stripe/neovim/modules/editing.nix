{pkgs, ...}: {
  programs.nixvim = {
    extraPlugins = (
      map pkgs.vimUtils.buildVimPlugin [
        {
          name = "payjectionist.nvim";
          src = builtins.fetchGit {
            url = "git@git.corp.stripe.com:nms/payjectionist.nvim.git";
            rev = "842ecafabb566979eb4cb688fa2f61199eaef8aa";
          };
        }
      ]
    );
  };
}
