# nix-instantiate --eval --strict --json tests/lab-network.nix --arg lib '(import <nixpkgs/lib>)'
{lib}: let
  inventory = builtins.fromJSON (builtins.readFile ../lab/network.json);
  read = value: import ../lab/network.nix {inherit lib; inventory = value;};
  network = read inventory;
  rejects = value: !(builtins.tryEval (builtins.deepSeq (read value) true)).success;
  changeMachine = hostname: changes: inventory // {
    machines = map (machine: if machine.hostname == hostname then machine // changes else machine) inventory.machines;
  };
  changeService = name: changes: inventory // {
    services = map (service: if service.name == name then service // changes else service) inventory.services;
  };
  mediaServices = [
    {name = "test-sonarr"; hostname = "test-sonarr"; machine = "media"; scheme = "http"; port = 8989;}
    {name = "test-radarr"; hostname = "test-radarr"; machine = "media"; scheme = "http"; port = 7878;}
  ];
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
        "192.168.1.204 builder.vm.netcat.cloud"
        "192.168.1.205 media.vm.netcat.cloud"
        "192.168.1.203 download.netcat.cloud"
        "192.168.1.203 plex.netcat.cloud"
        "192.168.1.203 trackers.netcat.cloud"
        "192.168.1.203 books.netcat.cloud"
        "192.168.1.203 auth.netcat.cloud"
        "192.168.1.203 torrents.netcat.cloud"
        "192.168.1.203 netcat.cloud"
        "192.168.1.203 gateway.netcat.cloud"
        "192.168.1.203 nas.netcat.cloud"
        "192.168.1.203 proxmox.netcat.cloud"
        "192.168.1.203 pihole.netcat.cloud"
        "192.168.1.203 tv.netcat.cloud"
        "192.168.1.203 movies.netcat.cloud"
        "192.168.1.203 music.netcat.cloud"
        "192.168.1.203 audiobooks.netcat.cloud"
        "192.168.1.203 usenet.netcat.cloud"
      ];
    };
    testAddressChangeReachesAllServiceRecords = {
      expr = builtins.all (line: lib.hasPrefix "192.168.1.206 " line)
        (builtins.filter (line: lib.hasSuffix "netcat.cloud" line && !(lib.hasInfix ".vm." line))
          (read (changeMachine "caddy" {ip = "192.168.1.206";})).dnsHosts);
      expected = true;
    };
    testAliasRename = {
      expr = (read (changeService "truenas" {hostname = "storage";})).servicesByName.truenas.fqdn;
      expected = "storage.netcat.cloud";
    };
    testApexHostname = {
      expr = network.servicesByName.homepage.fqdn;
      expected = "netcat.cloud";
    };
    testDuplicateApexRejected = {
      expr = rejects (changeService "truenas" {hostname = "@";});
      expected = true;
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
      expr = builtins.all (alias: rejects (changeService "truenas" {hostname = alias;}))
        ["" "NAS" "nas.example" "-nas" "nas-" "nas\nother" null];
      expected = true;
    };
    testDuplicateAlias = {
      expr = rejects (changeService "truenas" {hostname = "pihole";});
      expected = true;
    };
    testSeveralServicesOnOneMachine = {
      expr = let n = read (inventory // {services = inventory.services ++ mediaServices;}); in {
        sonarr = n.servicesByName.test-sonarr.upstream;
        radarr = n.servicesByName.test-radarr.upstream;
        records = lib.takeEnd 2 n.dnsHosts;
      };
      expected = {
        sonarr = "http://media.vm.netcat.cloud:8989";
        radarr = "http://media.vm.netcat.cloud:7878";
        records = ["192.168.1.203 test-sonarr.netcat.cloud" "192.168.1.203 test-radarr.netcat.cloud"];
      };
    };
    testExistingUpstreams = {
      expr = builtins.mapAttrs (_: service: service.upstream) network.servicesByName;
      expected = {
        prowlarr = "http://media.vm.netcat.cloud:9696";
        seerr = "http://media.vm.netcat.cloud:5055";
        plex = "http://media.vm.netcat.cloud:32400";
        calibre-web-automated = "http://media.vm.netcat.cloud:8083";
        gateway = "https://gateway.vm.netcat.cloud:443";
        qbittorrent = "http://media.vm.netcat.cloud:8080";
        sabnzbd = "http://media.vm.netcat.cloud:8085";
        homepage = "http://caddy.vm.netcat.cloud:8082";
        authentik = "http://caddy.vm.netcat.cloud:9000";
        truenas = "http://truenas.vm.netcat.cloud:80";
        proxmox = "https://proxmox.vm.netcat.cloud:8006";
        pihole-dns = "http://pihole-dns.vm.netcat.cloud:80";
        sonarr = "http://media.vm.netcat.cloud:8989";
        radarr = "http://media.vm.netcat.cloud:7878";
        lidarr = "http://media.vm.netcat.cloud:8686";
        audiobookshelf = "http://media.vm.netcat.cloud:8000";
      };
    };
    testServiceCanChangeBackend = {
      expr = (read (changeService "truenas" {machine = "media"; port = 8080;})).servicesByName.truenas;
      expected = {
        name = "truenas"; hostname = "nas"; machine = "media"; scheme = "http"; port = 8080;
        fqdn = "nas.netcat.cloud"; upstream = "http://media.vm.netcat.cloud:8080";
      };
    };
    testInvalidServices = {
      expr = builtins.all (changes: rejects (changeService "truenas" changes)) [
        {name = "gateway";} {name = "";} {name = null;} {name = "bad name";}
        {machine = "missing";} {machine = null;}
        {scheme = "ftp";} {scheme = null;}
        {port = 0;} {port = 65536;} {port = "80";} {port = 80.5;} {port = null;}
      ];
      expected = true;
    };
    testMissingServiceFields = {
      expr = builtins.all (field: rejects (inventory // {
        services = [(builtins.removeAttrs (builtins.head inventory.services) [field])];
      })) ["name" "hostname" "machine" "scheme" "port"];
      expected = true;
    };
    testMalformedServiceList = {
      expr = builtins.all (services: rejects (inventory // {inherit services;})) [null {} [null] ["service"]]
        && rejects (builtins.removeAttrs inventory ["services"]);
      expected = true;
    };
    testLegacyAliasesRejected = {
      expr = rejects (changeMachine "truenas" {public_hostname = "nas";});
      expected = true;
    };
    testEmptyServiceList = {
      expr = (read (inventory // {services = [];})).dnsHosts;
      expected = map (machine: "${machine.ip} ${machine.hostname}.vm.netcat.cloud") inventory.machines;
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
