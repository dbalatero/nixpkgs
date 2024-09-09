{
  programs.nixvim = {
    plugins.luasnip = {
      enable = true;
      settings = {
        history = true;
        enable_autosnippets = true;
      };
    };

    extraConfigLuaPost =
      /*
      lua
      */
      ''
        local ls = require("luasnip")
        ls.add_snippets("all", {
          ls.snippet("todo", { ls.text_node("TODO(dbalatero): ") }),
        })
      '';
  };
}
