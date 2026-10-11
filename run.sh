#!/usr/bin/env bash
# ==============================================================================
# LiquidCloud Launcher Script
# Automatically sets up the virtual environment & dependencies on first run!
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

# Check if mpv is installed
if ! command -v mpv &> /dev/null; then
    echo "❌ Error: 'mpv' is required for audio playback but not found in PATH."
    echo "Please install mpv:"
    echo "  Arch Linux:    sudo pacman -S mpv"
    echo "  Ubuntu/Debian: sudo apt install mpv"
    echo "  Fedora:        sudo dnf install mpv"
    exit 1
fi

# Ensure python3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: 'python3' is required but not installed."
    exit 1
fi

# Automatically bootstrap virtual environment on first run
if [ ! -f "$DIR/.venv/bin/python" ]; then
    echo "💧 LiquidCloud: Initializing virtual environment on first launch..."
    python3 -m venv "$DIR/.venv"
    echo "📦 Installing required dependencies (Textual, yt-dlp)..."
    "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
    echo "✅ Setup complete! Launching LiquidCloud..."
fi

# Launch application
exec "$DIR/.venv/bin/python" "$DIR/liquidcloud.py" "$@"
