{pkgs, ...}: {
  home.packages = with pkgs; [
    nodenv

    # system node + yarn
    nodejs_22
    yarn-berry
  ];

  programs.zsh.initContent = ''
    eval "$(${pkgs.nodenv}/bin/nodenv init -)"
  '';

  home.file.".nodenv/plugins" = {
    source = pkgs.linkFarm "nodenv-plugins" [
      {
        name = "node-build";
        path = pkgs.fetchFromGitHub {
          owner = "nodenv";
          repo = "node-build";
          rev = "v5.4.21";
          hash = "sha256-utmsh7syaExIeSStkruO/UHvfuth7JAVY3V2HzAVDzw=";
        };
      }
    ];
  };
}
