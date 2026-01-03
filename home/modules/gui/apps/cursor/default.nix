{
  config,
  lib,
  ...
}: {
  # Create writable symlinks to Cursor config files
  # This allows Cursor to modify the files, which will update your dotfiles directly
  # Changes made by Cursor will show up in git status and can be committed

  home.file."Library/Application Support/Cursor/User/settings.json".source =
    config.lib.file.mkOutOfStoreSymlink
      "${config.home.homeDirectory}/.config/nixpkgs/home/modules/gui/apps/cursor/settings.json";

  home.file."Library/Application Support/Cursor/User/keybindings.json".source =
    config.lib.file.mkOutOfStoreSymlink
      "${config.home.homeDirectory}/.config/nixpkgs/home/modules/gui/apps/cursor/keybindings.json";

  # Sync extensions bidirectionally
  home.activation.syncCursorExtensions = lib.hm.dag.entryAfter ["writeBoundary"] ''
    EXTENSIONS_FILE="${config.home.homeDirectory}/.config/nixpkgs/home/modules/gui/apps/cursor/extensions.txt"
    CURSOR_BIN="/opt/homebrew/bin/cursor"

    # Only proceed if cursor is installed
    if [ -x "$CURSOR_BIN" ]; then
      echo "Syncing Cursor extensions..."

      # Get currently installed extensions
      INSTALLED=$("$CURSOR_BIN" --list-extensions 2>/dev/null || echo "")

      # Export to dotfiles
      echo "$INSTALLED" > "$EXTENSIONS_FILE"
      echo "Exported $(echo "$INSTALLED" | wc -l | tr -d ' ') extensions"

      # Install any extensions from the list that aren't currently installed
      if [ -f "$EXTENSIONS_FILE" ]; then
        MISSING_COUNT=0
        while IFS= read -r extension; do
          # Skip empty lines and comments
          [[ -z "$extension" || "$extension" =~ ^# ]] && continue

          # Check if already installed
          if ! echo "$INSTALLED" | grep -q "^$extension$"; then
            echo "Installing missing extension: $extension"
            $DRY_RUN_CMD "$CURSOR_BIN" --install-extension "$extension" --force 2>/dev/null || true
            MISSING_COUNT=$((MISSING_COUNT + 1))
          fi
        done < "$EXTENSIONS_FILE"

        if [ $MISSING_COUNT -eq 0 ]; then
          echo "All extensions already installed"
        fi
      fi
    else
      echo "Cursor not installed at $CURSOR_BIN, skipping extension sync"
    fi
  '';
}
