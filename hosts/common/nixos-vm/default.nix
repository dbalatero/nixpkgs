{config, inputs, lib, pkgs, modulesPath, ...}: {
  imports = [
    (modulesPath + "/profiles/qemu-guest.nix")
    inputs.home-manager.nixosModules.home-manager
    ../nixos/nix-ld.nix
  ];

  # Keep PDE dependencies identical in the image and generated VM hosts.
  nixpkgs = {
    config.allowUnfree = true;
    overlays = [
      inputs.claude-code.overlays.default
      inputs.codex-cli.overlays.default
      inputs.neovim-nightly-overlay.overlays.default
    ];
  };
  home-manager = {
    useGlobalPkgs = true;
    useUserPackages = true;
    extraSpecialArgs = {inherit inputs;};
  };
  programs.zsh.enable = true;
  programs.zsh.enableCompletion = false;

  # Keep this reusable by both the image and bootstrapped hosts. The image
  # variant or generated hardware module supplies filesystems and bootloader.
  boot.growPartition = true;
  fileSystems."/".autoResize = true;
  boot.kernelParams = ["console=tty0" "console=ttyS0,115200n8"];

  networking.useDHCP = lib.mkDefault true;
  networking.useNetworkd = true;
  # Updating /etc/hostname alone leaves the running kernel's name unchanged.
  # Apply the declared VM name during switch as well as on the next boot.
  system.activationScripts.vm-hostname = lib.mkIf (config.networking.hostName != "")
    (lib.stringAfter ["etc"] ''
      ${pkgs.hostname}/bin/hostname -- ${lib.escapeShellArg config.networking.hostName}
    '');
  services.qemuGuest.enable = true;
  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
      PermitRootLogin = "no";
    };
  };

  # Never use the common desktop account's initialPassword. A missing injected
  # hash leaves the account password locked in the secret-free image.
  users.mutableUsers = false;
  users.users.dbalatero = {
    isNormalUser = true;
    uid = 1000;
    group = "users";
    description = "David Balatero";
    shell = pkgs.zsh;
    extraGroups = ["wheel"];
    hashedPasswordFile = "/etc/nixos-vm/recovery-password.hash";
    openssh.authorizedKeys.keyFiles = [../../proxmox-base/authorized_keys];
  };
  security.sudo.wheelNeedsPassword = false;

  nix.settings.experimental-features = ["nix-command" "flakes"];
  environment.systemPackages = with pkgs; [
    git
    vim
    python3
    openssh
    curl
    dig
    jq
    parted
  ];
  environment.variables.EDITOR = "vim";
  time.timeZone = lib.mkDefault "America/New_York";
  i18n.defaultLocale = "en_US.UTF-8";
  system.stateVersion = "25.11";
}
