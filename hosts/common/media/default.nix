{...}: {
  # Keep media ownership and access consistent across hosts.
  users.groups.media.gid = 2000;
  users.users.dbalatero.extraGroups = ["media"];
}
