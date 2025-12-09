{pkgs, ...}: {
  programs.zsh.initContent = ''
    if command -v nodenv &> /dev/null; then
      eval "$(nodenv init -)"
    fi
  '';
}
