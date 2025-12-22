{
  # config,
  pkgs,
  ...
}: {
  imports = [
    ./claude.nix
    ./completion.nix
    ./editing.nix
    ./fzf-lua.nix
    ./git.nix
    ./lsp.nix
    ./testing.nix
    ./treesitter.nix
    ./tmux.nix
    ./ui.nix
  ];

  programs.nixvim.plugins = {
    nix.enable = true;
  };

  programs.nixvim.extraPlugins = with pkgs;
    (
      with vimPlugins; [
        plenary-nvim # Useful Lua functions
      ]
    )
    ++ (
      map vimUtils.buildVimPlugin [
        # {
        #   # disable highlights automatically on cursor move
        #   name = "vim-cool";
        #   src = fetchFromGitHub {
        #     owner = "romainl";
        #     repo = "vim-cool";
        #     rev = "662e7b11064cbeedad17c45d2fe926e78d3cd0b6";
        #     hash = "sha256-M91iWqytUR6AldM2H4U/79nX2ba5gN4I/z7m0iltjcY=";
        #   };
        # }
      ]
    );
}
