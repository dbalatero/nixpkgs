{config, lib, pkgs, ...}: let
  network = import ../../lab/network.nix {inherit lib;};
  port = network.servicesByName.bazarr.port;
  python = pkgs.python3.withPackages (ps: [ps.pyyaml]);
  settings = pkgs.writeText "bazarr-defaults.json" (builtins.toJSON {
    dataDir = config.services.bazarr.dataDir;
    inherit port;
    apps = lib.genAttrs ["sonarr" "radarr"] (name: {
      port = network.servicesByName.${name}.port;
    });
    config = {
      general = {
        ip = "0.0.0.0";
        auto_update = false;
        debug = false;
        use_embedded_subs = true;
        embedded_subtitles_parser = "ffprobe";
        ignore_pgs_subs = false;
        ignore_vobsub_subs = false;
        # ASS does not necessarily imply moving subtitles; accept embedded English.
        ignore_ass_subs = false;
        default_und_embedded_subtitles_lang = "";
        single_language = false;
        subzero_mods = "remove_tags";
        subfolder = "current";
        chmod_enabled = true;
        chmod = "0660";
        minimum_score = 90;
        minimum_score_movie = 70;
        upgrade_subs = true;
        upgrade_manual = false;
        days_to_upgrade_subs = 30;
        upgrade_frequency = 12;
        wanted_search_frequency = 6;
        wanted_search_frequency_movie = 6;
        use_sonarr = true;
        use_radarr = true;
      };
      auth.type = null; # Caddy's Authentik gate; backend restricted to Caddy.
      analytics.enabled = false;
    };
    # Preserve additional providers and their credentials configured in the UI.
    # Bazarr ranks matches by subtitle score, not provider list order.
    # OpenSubtitles.com credentials/VIP status belong to the runtime account.
    providers = ["opensubtitlescom" "yifysubtitles"];
    disabledProviders = ["gestdown" "tvsubtitles"];
    profile = {
      name = "English (Nix)";
      cutoff = 1;
      items = [{
        id = 1;
        language = "en";
        forced = "False";
        hi = "False";
        audio_exclude = "False";
        audio_only_include = "False";
      }];
      mustContain = [];
      mustNotContain = [];
      originalFormat = false;
      tag = null;
    };
  });
  proxyRule = "-i ens18 -s ${network.proxy.ip}/32 -p tcp --dport ${toString port} -j nixos-fw-accept";
in {
  services.bazarr = {
    enable = true;
    listenPort = port;
    openFirewall = false;
    group = "media";
    # Bazarr already emits the same records to stderr. Keep only that handler:
    # journald compresses and caps all runtime/setup logs at 512M/128M/14 days
    # (common/nfs). No file logs or per-job logs need external rotation.
    package = pkgs.bazarr.overrideAttrs (old: {
      postPatch = (old.postPatch or "") + ''
        substituteInPlace bazarr/app/logger.py \
          --replace-fail 'logger.addHandler(fh)' 'fh.close() # Nix: journal owns retention'
      '';
    });
  };
  networking.firewall.extraCommands = "iptables -A nixos-fw ${proxyRule}";
  networking.firewall.extraStopCommands = "iptables -D nixos-fw ${proxyRule} 2>/dev/null || true";
  systemd.services.bazarr = {
    requires = ["media-library-directories.service" "sonarr.service" "radarr.service"];
    after = ["media-library-directories.service" "sonarr.service" "radarr.service"];
    unitConfig.RequiresMountsFor = ["/mnt/warez"];
    serviceConfig = {
      UMask = "0007";
      RestartSec = 15;
      LoadCredential = map (name: "${name}.xml:${config.services.${name}.dataDir}/config.xml") ["sonarr" "radarr"];
    };
    preStart = ''
      ${python}/bin/python ${./bazarr-configure.py} ${settings} config
    '';
  };
  systemd.services.bazarr-profiles = {
    description = "Reconcile Bazarr English profile for existing and future media";
    requires = ["bazarr.service"];
    after = ["bazarr.service"];
    serviceConfig = {
      Type = "oneshot";
      User = "bazarr";
      Group = "media";
      UMask = "0077";
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
      ExecStart = "${python}/bin/python ${./bazarr-configure.py} ${settings} profiles";
    };
  };
  systemd.timers.bazarr-profiles = {
    wantedBy = ["timers.target"];
    timerConfig = {OnBootSec = "1min"; OnUnitInactiveSec = "5min";};
  };
}
