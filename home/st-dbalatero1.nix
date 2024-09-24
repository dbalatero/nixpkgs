{ config, lib, pkgs, ... }:

{
  imports = [
    ./modules/common.nix
    ./modules/darwin
  ];

  home.homeDirectory = "/Users/dbalatero";
  home.username = "dbalatero";

  programs.git.userEmail = "dbalatero@stripe.com";

  programs.zsh.initExtra = ''
    ### BEGIN STRIPE
    # All Stripe related shell configuration
    # is at ~/.stripe/shellinit/zshrc and is
    # persistently managed by Chef. You shouldn't
    # remove this unless you don't want to load
    # Stripe specific shell configurations.
    #
    # Feel free to add your customizations in this
    # file (~/.zshrc) after the Stripe config
    # is sourced.
    if [[ -f ~/.stripe/shellinit/zshrc ]]; then
      source ~/.stripe/shellinit/zshrc
    fi
    ### END STRIPE
  '';
}
