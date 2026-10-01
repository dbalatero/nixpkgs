{...}: {
  # Match the NAS group ID so NFS clients share media write permissions.
  users.groups.media.gid = 2000;
  users.users.dbalatero.extraGroups = ["media"];
}
