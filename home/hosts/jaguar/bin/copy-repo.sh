#!/usr/bin/env bash
set -euo pipefail

# Change this to your path
SOURCE="$HOME/code/monologue"

if [ ! -d "$SOURCE" ]; then
  echo "Error: source repo $SOURCE does not exist"
  exit 1
fi

read -rp "New repo name: " name
if [ -z "$name" ]; then
  echo "Error: name cannot be empty"
  exit 1
fi

TARGET="$HOME/code/$name"

if [ -e "$TARGET" ]; then
  echo "Error: $TARGET already exists"
  exit 1
fi

echo "Cloning $SOURCE -> $TARGET..."
git clone "$SOURCE" "$TARGET"

echo "Setting origin to github..."
git -C "$TARGET" remote set-url origin git@github.com:withgraphite/monologue.git

echo "Symlinking .envrc..."
ln -sf "$SOURCE/.envrc" "$TARGET/.envrc"

read -rp "Run ./setup.sh in $TARGET? [y/N] " run_setup
if [ "$run_setup" = "y" ] || [ "$run_setup" = "Y" ]; then
  cd "$TARGET"
  ./setup.sh
fi

echo "Done! Repo is at $TARGET"
