{pkgs, ...}: {
  home.packages = with pkgs; [
    nodenv

    # system node + yarn
    nodejs_22
    yarn-berry
  ];

  programs.zsh.initExtra = ''
    eval "$(${pkgs.nodenv}/bin/nodenv init -)"
  '';

  home.file.".nodenv/plugins" = {
    source = pkgs.linkFarm "nodenv-plugins" [
      {
        name = "node-build";
        path = pkgs.fetchFromGitHub {
          owner = "nodenv";
          repo = "node-build";
          rev = "v5.3.11";
          hash = "sha256-yqYAKm4kYSxhrsOpM8+h6DDQrR7sHCrSWJ0e1wzyLPY=";
        };
      }
    ];
  };
}
