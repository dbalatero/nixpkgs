{
  programs.nixvim = {
    plugins = {
      neotest = {
        enable = true;

        adapters.jest.enable = true;
      };
    };
  };
}
