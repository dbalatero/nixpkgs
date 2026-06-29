{...}: {
  # Enable ssh-agent service
  services.ssh-agent.enable = true;

  programs.ssh = {
    enable = true;

    settings = {
      "*" = {
        AddKeysToAgent = "yes";
      };

      "github.com" = {
        IdentityFile = "~/.ssh/id_github";
      };

      "pumpkin" = {
        HostName = "pumpkin.whatbox.ca";
        User = "dbalatero";
      };
    };
  };
}
