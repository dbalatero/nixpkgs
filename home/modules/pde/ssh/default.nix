{...}: {
  # Enable ssh-agent service
  services.ssh-agent.enable = true;

  programs.ssh = {
    enable = true;

    matchBlocks = {
      "*" = {
        addKeysToAgent = "yes";
      };

      "github.com" = {
        identityFile = "~/.ssh/id_github";
      };
    };
  };
}
