{modulesPath, ...}: {
  imports = [../common/nixos-vm];
  networking.hostName = "nixos-base";

  home-manager.users.dbalatero.imports = [../../home/modules/proxmox-vm];

  # The pinned nixpkgs calls this variant qemu-efi. Keep qcow as our public
  # image interface: GPT, ESP plus a growable ext4 root, and OVMF firmware.
  image.modules.qcow = {
    imports = [(modulesPath + "/virtualisation/disk-image.nix")];
    image = {
      format = "qcow2";
      efiSupport = true;
      baseName = "nixos-proxmox-base";
    };
    virtualisation.diskSize = 20 * 1024;
    boot.loader.efi.canTouchEfiVariables = false;
  };
}
