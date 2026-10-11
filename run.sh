#!/usr/bin/env bash
# LiquidCloud Launcher Script

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

# Check if mpv is installed
if ! command -v mpv &> /dev/null; then
    echo "Error: 'mpv' is required for playback but not found in PATH."
    echo "Please install mpv:"
    echo "  Arch Linux: sudo pacman -S mpv"
    echo "  Ubuntu/Debian: sudo apt install mpv"
    exit 1
fi

# Use virtualenv python if available
if [ -f "$DIR/.venv/bin/python" ]; then
    exec "$DIR/.venv/bin/python" "$DIR/liquidcloud.py" "$@"
else
    exec python3 "$DIR/liquidcloud.py" "$@"
fi
