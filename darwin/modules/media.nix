{config, ...}: {
  # Match the NAS group ID so NFS clients share media write permissions.
  users.knownGroups = ["media"];
  users.groups.media = {
    gid = 2000;
    members = [config.system.primaryUser];
  };
}
