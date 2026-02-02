{ pkgs, ... }:

{
  home.file.".psqlrc".text = ''
    \set PROMPT1 '%~%x%# '
    \x auto
    \set ON_ERROR_STOP ON
    \set ON_ERROR_ROLLBACK interactive

    \pset null '''
    \pset linestyle 'unicode'
    \pset unicode_border_linestyle single
    \pset unicode_column_linestyle single
    \pset unicode_header_linestyle double
    set intervalstyle to 'postgres_verbose';

    \setenv LESS '-iMFXSx4R'
    \setenv EDITOR '${pkgs.neovim}/bin/nvim'
  '';
}
