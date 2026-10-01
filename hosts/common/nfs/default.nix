{...}: {
  imports = [../media];

  fileSystems."/mnt/warez" = {
    device = "truenas.vm.netcat.cloud:/mnt/warez/data";
    fsType = "nfs";
    options = [
      "nfsvers=4.2"
      "proto=tcp"
      "hard"
      "_netdev"
      "nofail"
      "x-systemd.automount"
      "x-systemd.mount-timeout=30s"
      "x-systemd.idle-timeout=10min"
    ];
  };

  # Mount units and NFS client diagnostics log to the journal only.
  # These host-wide limits bound journal storage; age retention is additional.
  services.journald.extraConfig = ''
    SystemMaxUse=512M
    RuntimeMaxUse=128M
    MaxRetentionSec=14day
  '';
}
