{config, ...}: let
  inventory = builtins.fromJSON (builtins.readFile ../../lab/network.json);
in {
  # Generate secrets on the server, never during evaluation or in the store.
  systemd.services.builder-cache-key = {
    description = "Provision the builder binary cache signing key";
    before = ["nix-serve.service"];
    requiredBy = ["nix-serve.service"];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      StateDirectory = "nix-cache";
      StateDirectoryMode = "0700";
      UMask = "0077";
    };
    script = ''
      set -eu
      if [ ! -s /var/lib/nix-cache/cache-key.sec ]; then
        ${config.nix.package}/bin/nix-store --generate-binary-cache-key \
          builder.vm.netcat.cloud-1 /var/lib/nix-cache/cache-key.sec /var/lib/nix-cache/cache-key.pub
      fi
      test -s /var/lib/nix-cache/cache-key.pub
    '';
  };
  services.nix-serve = {
    enable = true;
    bindAddress = "127.0.0.1";
    secretKeyFile = "/var/lib/nix-cache/cache-key.sec";
  };
  services.nginx = {
    enable = true;
    virtualHosts."builder.vm.netcat.cloud" = {
      default = true;
      locations."/".proxyPass = "http://127.0.0.1:5000";
    };
  };
  networking.firewall.extraCommands = ''
    iptables -A nixos-fw -s ${inventory.subnet} -p tcp --dport 80 -j nixos-fw-accept
  '';
  networking.firewall.extraStopCommands = ''
    iptables -D nixos-fw -s ${inventory.subnet} -p tcp --dport 80 -j nixos-fw-accept 2>/dev/null || true
  '';
}
