{inputs, lib, pkgs, ...}: {
  # The image and every bootstrapped VM share the complete terminal PDE.
  imports = [
    ../core
    ../pde
    inputs.nixvim.homeModules.nixvim
    inputs.stylix.homeModules.stylix
  ];

  home.username = "dbalatero";
  home.homeDirectory = "/home/dbalatero";
  dconf.enable = false;

  # Home Manager owns SSH configuration; preparation injects only private key
  # material and known_hosts, outside the Nix store.
  programs.ssh.settings."github.com" = {
    IdentityFile = lib.mkForce "~/.ssh/id_nixos_vm_github";
    User = "git";
    IdentitiesOnly = "yes";
    IdentityAgent = "none";
    StrictHostKeyChecking = "yes";
    AddKeysToAgent = "no";
  };

  # NixOS installs this home profile under /etc/profiles/per-user, not
  # ~/.nix-profile. Use the declared shell directly in tmux.
  programs.tmux.shell = lib.mkForce "${pkgs.zsh}/bin/zsh";

  # Rebuild the canonical checkout without merging another remote branch.
  programs.zsh.shellAliases.switch = lib.mkForce
    "(cd ~/.config/nixpkgs && ./bin/switch)";
}
