{
  config,
  lib,
  pkgs,
  ...
}: {
  # SSH daemon configuration
  # Hardening applied from: https://dev-sec.io/baselines/ssh/
  services.openssh = {
    enable = true;

    settings = {
      # Authentication
      PermitRootLogin = "no";
      PasswordAuthentication = false;
      PermitEmptyPasswords = false;
      ChallengeResponseAuthentication = false;
      KbdInteractiveAuthentication = false;
      GSSAPIAuthentication = false;
      KerberosAuthentication = false;
      PubkeyAuthentication = true;

      # Security hardening
      StrictModes = true;
      MaxAuthTries = 3;
      MaxSessions = 10;
      LoginGraceTime = 30;

      # Session keepalive (30 min idle timeout: 600s * 3 = 1800s)
      ClientAliveInterval = 600;
      ClientAliveCountMax = 3;
      TCPKeepAlive = false;

      # Disable unnecessary features
      X11Forwarding = false;
      AllowTcpForwarding = "no";
      AllowAgentForwarding = "no";
      PermitTunnel = "no";
      GatewayPorts = "no";
      PermitUserEnvironment = false;

      # Logging
      LogLevel = "VERBOSE";

      # Use strong cryptography (NixOS defaults are already good, but being explicit)
      Ciphers = [
        "chacha20-poly1305@openssh.com"
        "aes256-gcm@openssh.com"
        "aes128-gcm@openssh.com"
        "aes256-ctr"
        "aes192-ctr"
        "aes128-ctr"
      ];

      KexAlgorithms = [
        "curve25519-sha256"
        "curve25519-sha256@libssh.org"
        "diffie-hellman-group-exchange-sha256"
      ];

      Macs = [
        "hmac-sha2-512-etm@openssh.com"
        "hmac-sha2-256-etm@openssh.com"
        "umac-128-etm@openssh.com"
      ];
    };
  };

  # Open SSH port in the firewall
  networking.firewall.allowedTCPPorts = [ 22 ];
}
