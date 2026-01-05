# MangoHud Configuration

MangoHud is a performance overlay for games that shows FPS, frame times, CPU/GPU usage, temperatures, and more.

## Keybinds

- **Right Shift + F12**: Toggle MangoHud overlay visibility
- **Left Shift + F2**: Toggle performance logging (saves metrics to file)

## What's Displayed

The overlay shows:
- **FPS**: Current frames per second
- **Frame timing**: Graph showing frame time consistency
- **GPU stats**: Temperature, core/memory clocks, power usage, load
- **CPU stats**: Temperature, power usage, per-core load
- **RAM/VRAM**: Memory usage
- **Wine/Proton version**: For Steam games running through compatibility layer
- **Engine version**: Game engine information
- **Resolution**: Current display resolution

## Position & Appearance

- Position: Top-left corner
- Background transparency: 50%
- Font size: 24pt

## Performance Logging

When you enable logging with **Left Shift + F2**, MangoHud will save performance metrics to:
`~/mangohud-logs/`

This is useful for:
- Analyzing performance issues
- Benchmarking different settings
- Comparing performance across game updates

## Using MangoHud

### Automatic (Recommended for Steam)

MangoHud can be enabled globally in Steam:
1. Open Steam
2. Go to Settings → In-Game
3. Set "Enable Steam Overlay" to ON
4. In launch options for a game, add: `mangohud %command%`

Or enable it globally for all Steam games by setting in `~/.profile`:
```bash
export MANGOHUD=1
```

### Manual Launch

For non-Steam games, prefix the game command with `mangohud`:
```bash
mangohud ./game
```

## Configuration

The configuration file is managed by home-manager at:
`home/modules/gui/nixos/mangohud/default.nix`

After editing, run `./bin/switch` to apply changes.

## Customization

Uncomment and modify the color settings in `default.nix` to customize:
- GPU color
- CPU color
- VRAM color
- RAM color
- Frame time color
- Background color
- Text color

All colors are in hex format (e.g., `2e97cb` for blue).
