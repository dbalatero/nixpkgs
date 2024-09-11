{self, ...}: {
  services.nix-daemon.enable = true;

  nix.settings.experimental-features = "nix-command flakes";
  nix.settings.trusted-users = ["dbalatero"];

  system.configurationRevision = self.rev or self.dirtyRev or null;
  nixpkgs.hostPlatform = "aarch64-darwin";
  nixpkgs.config.allowUnfree = true;
}
