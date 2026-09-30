# nix-instantiate --eval --strict --json tests/lab-network.nix --arg lib '(import <nixpkgs/lib>)'
{lib}: let
  inventory = builtins.fromJSON (builtins.readFile ../lab/network.json);
  read = value: import ../lab/network.nix {inherit lib; inventory = value;};
  network = read inventory;
  rejects = value: !(builtins.tryEval (builtins.deepSeq (read value) true)).success;
  changeMachine = hostname: changes: inventory // {
    machines = map (machine: if machine.hostname == hostname then machine // changes else machine) inventory.machines;
  };
  searchFor = hostname: (lib.evalModules {
    modules = [
      ../hosts/common/lab-network
      {
        options.networking = {
          hostName = lib.mkOption {type = lib.types.str;};
          search = lib.mkOption {type = lib.types.listOf lib.types.str; default = [];};
        };
        config.networking.hostName = hostname;
      }
    ];
  }).config.networking.search;
  cases = {
    testDirectAndServiceRecords = {
      expr = network.dnsHosts;
      expected = [
        "192.168.1.1 gateway.vm.netcat.cloud"
        "192.168.1.169 pihole-legacy.vm.netcat.cloud"
        "192.168.1.201 truenas.vm.netcat.cloud"
        "192.168.1.209 imessage.vm.netcat.cloud"
        "192.168.1.250 proxmox.vm.netcat.cloud"
        "192.168.1.202 pihole-dns.vm.netcat.cloud"
        "192.168.1.203 caddy.vm.netcat.cloud"
        "192.168.1.203 gateway.netcat.cloud"
        "192.168.1.203 nas.netcat.cloud"
        "192.168.1.203 pihole.netcat.cloud"
      ];
    };
    testAddressChangeReachesAllServiceRecords = {
      expr = builtins.all (line: lib.hasPrefix "192.168.1.204 " line)
        (builtins.filter (line: lib.hasSuffix "netcat.cloud" line && !(lib.hasInfix ".vm." line))
          (read (changeMachine "caddy" {ip = "192.168.1.204";})).dnsHosts);
      expected = true;
    };
    testAliasRename = {
      expr = (read (changeMachine "truenas" {public_hostname = "storage";})).machinesByName.truenas.serviceFqdn;
      expected = "storage.netcat.cloud";
    };
    testSharedSearchOnLabHosts = {
      expr = map searchFor ["pihole-dns" "caddy"];
      expected = [["vm.netcat.cloud"] ["vm.netcat.cloud"]];
    };
    testNoSearchOnBaseOrUnlistedHosts = {
      expr = map searchFor ["proxmox-base" "unlisted-vm"];
      expected = [[] []];
    };
    testInvalidAliases = {
      expr = builtins.all (alias: rejects (changeMachine "truenas" {public_hostname = alias;}))
        ["" "NAS" "nas.example" "-nas" "nas-" "nas\nother" null];
      expected = true;
    };
    testDuplicateAlias = {
      expr = rejects (changeMachine "truenas" {public_hostname = "pihole";});
      expected = true;
    };
    testInvalidMachineName = {
      expr = rejects (changeMachine "imessage" {hostname = "bad name";});
      expected = true;
    };
    testDuplicateMachineName = {
      expr = rejects (changeMachine "imessage" {hostname = "truenas";});
      expected = true;
    };
    testInvalidAndDuplicateIP = {
      expr = builtins.all (ip: rejects (changeMachine "imessage" {inherit ip;}))
        ["192.168.1.999" "192.168.1.201" "192.168.1.209 injected" "192.168.01.209"];
      expected = true;
    };
    testMissingProxy = {
      expr = rejects (inventory // {reverse_proxy_hostname = "missing";});
      expected = true;
    };
    testInvalidDomain = {
      expr = rejects (inventory // {domain = "netcat.cloud.";});
      expected = true;
    };
    testMetadataPreserved = {
      expr = (read (changeMachine "imessage" {documentation_only = true;})).machinesByName.imessage.documentation_only;
      expected = true;
    };
    testNetworkParameters = {
      expr = {inherit (network) prefixLength gateway dns;};
      expected = {prefixLength = 24; gateway = "192.168.1.1"; dns = ["192.168.1.202"];};
    };
  };
  failures = lib.runTests cases;
in
  if failures == [] then {passed = builtins.length (builtins.attrNames cases);}
  else throw (builtins.toJSON failures)
