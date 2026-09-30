{config, lib, ...}: {
  options.lab.nixBuildClient.enable = lib.mkEnableOption "the shared LAN Nix builder and signed cache";
  config = lib.mkIf config.lab.nixBuildClient.enable {
    assertions = [{
      assertion = config.networking.hostName != "builder";
      message = "The builder must not import nix-build-client.";
    }];
    programs.ssh.knownHosts."builder.vm.netcat.cloud" = {
      hostNames = ["builder.vm.netcat.cloud" "192.168.1.204"];
      publicKeyFile = ./host-key.pub;
    };
    programs.ssh.extraConfig = ''
      Host builder.vm.netcat.cloud
        StrictHostKeyChecking yes
        IdentitiesOnly yes
        BatchMode yes
        ConnectTimeout 10
    '';
    nix.distributedBuilds = true;
    nix.buildMachines = [{
      hostName = "builder.vm.netcat.cloud";
      protocol = "ssh-ng";
      sshUser = "remotebuild";
      sshKey = "/root/.ssh/builder";
      system = "x86_64-linux";
      maxJobs = 2;
      supportedFeatures = ["benchmark" "big-parallel"];
    }];
    nix.settings = {
      builders-use-substitutes = true;
      max-jobs = lib.mkDefault 1;
      extra-substituters = ["http://builder.vm.netcat.cloud"];
      extra-trusted-public-keys = [
        (lib.trim (builtins.readFile ./cache-key.pub))
      ];
    };
  };
}
