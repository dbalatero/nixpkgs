{
  config,
  lib,
  pkgs,
  ...
}: {
  # Enable ssh-agent service
  services.ssh-agent.enable = true;

  programs.ssh = {
    enable = true;

    # Automatically add keys to agent when first used (for all hosts)
    matchBlocks = {
      "*" = {
        addKeysToAgent = "yes";
      };
    };

    # Configure your GitHub SSH key (ignored if file doesn't exist)
    extraConfig = ''
      IdentityFile ~/.ssh/id_github
    '';
  };
}
