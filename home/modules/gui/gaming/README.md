# Gaming Configuration

## Logitech G502 Mouse Configuration

The G502 settings are stored in the mouse's onboard memory and persist across reboots. However, if you need to reconfigure or the settings get reset, use these commands:

### Current Settings
- **DPI**: 5000
- **Polling Rate**: 1000Hz
- **LED Color**: Red (ff0000)
- **Profile Cycle Button**: Disabled

### Apply Configuration to All Profiles

```bash
# Set DPI, polling rate, and LEDs for all profiles
for i in 0 1 2 3 4; do
  ratbagctl hollering-marmot profile $i resolution 0 dpi set 5000
  ratbagctl hollering-marmot profile $i resolution 0 enabled set
  ratbagctl hollering-marmot profile $i resolution active set 0
  ratbagctl hollering-marmot profile $i rate set 1000
  ratbagctl hollering-marmot profile $i led 0 set mode on color ff0000
  ratbagctl hollering-marmot profile $i led 1 set mode on color ff0000
done

# Disable profile cycle button on active profile
ratbagctl hollering-marmot profile 2 button 8 action set disabled
```

### Useful Commands

```bash
# List available mice
ratbagctl list

# Check current configuration
ratbagctl hollering-marmot info

# Check active profile
ratbagctl hollering-marmot profile active get

# Change DPI (example: 5000)
for i in 0 1 2 3 4; do
  ratbagctl hollering-marmot profile $i resolution 0 dpi set 5000
done
```

### Mouse Button Mappings

The G502 has 11 buttons. Current profile 2 mappings:
- Button 0-4: Standard mouse buttons (left, right, middle, side buttons)
- Button 5: Resolution cycle (was "second-mode", changed to prevent issues)
- Button 6: Macro (Ctrl+C)
- Button 7: Macro (Ctrl+V)
- Button 8: Profile cycle (DISABLED)
- Button 9-10: Wheel left/right

## Half-Life Configuration

The Half-Life userconfig is automatically deployed to:
`~/.local/share/Steam/steamapps/common/Half-Life/valve/userconfig.cfg`

Key settings for optimal mouse feel:
- `m_rawinput 1` - Raw mouse input (bypasses OS acceleration)
- `m_filter 0` - No mouse smoothing
- `m_customaccel 0` - No custom acceleration
- `m_mouseaccel1 0`, `m_mouseaccel2 0` - No acceleration

Edit the config at:
`home/modules/gui/gaming/half-life/userconfig.cfg`

Then run `./bin/switch` to deploy changes.
