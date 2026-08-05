{pkgs, ...}: {
  home.packages = [
    (pkgs.writeShellScriptBin "BasiliskII" ''
      export GSETTINGS_SCHEMA_DIR="${pkgs.gtk3}/share/gsettings-schemas/${pkgs.gtk3.name}/glib-2.0/schemas"
      exec ${pkgs.basiliskii}/bin/BasiliskII "$@"
    '')
  ];

  home.file.".basilisk_ii_prefs".text = ''
    rom /mnt/storage/Emulation/MacOS/ROMs/quadra-centris-610-650-800.rom
    # disk /mnt/storage/Emulation/MacOS/InstallMedia/mac-os-7.6-cd.image
    disk */mnt/storage/Emulation/MacOS/InstallMedia/stuffit-expander-5.5-flat.img
    disk /mnt/storage/Emulation/MacOS/Disks/mac-os-7.6.hfv
    extfs /mnt/storage/Emulation/MacOS/Shared
    screen dga/1024/768
    scale_integer true
    scale_nearest true
    init_grab true
    seriala /dev/null
    serialb /dev/null
    bootdrive 0
    bootdriver 0
    ramsize 134217728
    frameskip 0
    modelid 5
    cpu 3
    fpu true
    nocdrom false
    nosound false
    noclipconversion false
  '';
}
