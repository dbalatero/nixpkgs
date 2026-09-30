# Shared inventory interpretation for DNS, lab clients, and the reverse proxy.
{lib, inventory ? builtins.fromJSON (builtins.readFile ./network.json)}: let
  validLabel = value:
    builtins.isString value
    && builtins.stringLength value <= 63
    && builtins.match "[a-z0-9]([a-z0-9-]*[a-z0-9])?" value != null;
  validDomain = value:
    builtins.isString value
    && builtins.stringLength value <= 253
    && builtins.all validLabel (lib.splitString "." value);
  validIPv4 = value:
    builtins.isString value
    && builtins.length (lib.splitString "." value) == 4
    && builtins.all (part:
      builtins.match "0|[1-9][0-9]{0,2}" part != null
      && lib.toInt part <= 255
    ) (lib.splitString "." value);
  unique = values: builtins.length values == builtins.length (lib.unique values);
  machines = inventory.machines;
  names = map (machine: machine.hostname) machines;
  services = builtins.filter (machine: machine ? public_hostname) machines;
  aliases = map (machine: machine.public_hostname) services;
  domain = inventory.domain;
  machineDomain = "${inventory.machine_subdomain}.${domain}";
  subnetParts = lib.splitString "/" inventory.subnet;
  prefixLength = lib.toInt (builtins.elemAt subnetParts 1);
  machinesByName = builtins.listToAttrs (map (machine: {
    name = machine.hostname;
    value = machine // {
      fqdn = "${machine.hostname}.${machineDomain}";
      serviceFqdn = if machine ? public_hostname then "${machine.public_hostname}.${domain}" else null;
    };
  }) machines);
  proxy = machinesByName.${inventory.reverse_proxy_hostname};
in
assert lib.assertMsg (validDomain domain && validLabel inventory.machine_subdomain && validDomain machineDomain)
  "lab/network.json: invalid domain or machine_subdomain";
assert lib.assertMsg (builtins.all validLabel names && unique names)
  "lab/network.json: invalid or duplicate machine hostname";
assert lib.assertMsg (builtins.all validLabel aliases && unique aliases)
  "lab/network.json: invalid or duplicate public_hostname";
assert lib.assertMsg (builtins.all (machine: validDomain "${machine.hostname}.${machineDomain}") machines)
  "lab/network.json: machine FQDN exceeds DNS limits";
assert lib.assertMsg (builtins.all (alias: validDomain "${alias}.${domain}") aliases)
  "lab/network.json: service FQDN exceeds DNS limits";
assert lib.assertMsg (builtins.all (machine: validIPv4 machine.ip) machines && unique (map (machine: machine.ip) machines))
  "lab/network.json: invalid or duplicate machine IPv4 address";
assert lib.assertMsg (validLabel inventory.reverse_proxy_hostname && builtins.hasAttr inventory.reverse_proxy_hostname machinesByName)
  "lab/network.json: reverse_proxy_hostname must name an inventory machine";
assert lib.assertMsg (builtins.length subnetParts == 2 && validIPv4 (builtins.head subnetParts) && prefixLength >= 0 && prefixLength <= 32 && validIPv4 inventory.gateway)
  "lab/network.json: invalid subnet or gateway";
{
  inherit domain machineDomain machinesByName proxy prefixLength;
  inherit (inventory) gateway dns;
  dnsHosts =
    map (machine: "${machine.ip} ${machinesByName.${machine.hostname}.fqdn}") machines
    ++ map (machine: "${proxy.ip} ${machinesByName.${machine.hostname}.serviceFqdn}") services;
}
