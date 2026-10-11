#!/usr/bin/env bash
# ==============================================================================
# LiquidCloud Launcher Script
# Automatically sets up the virtual environment & dependencies on first run!
# ==============================================================================
set -e

# Resolve symlinks to find the actual project directory
if command -v realpath &>/dev/null; then
    SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
else
    SCRIPT_PATH="${BASH_SOURCE[0]}"
    while [ -h "$SCRIPT_PATH" ]; do
        TARGET="$(readlink "$SCRIPT_PATH")"
        if [[ $TARGET == /* ]]; then
            SCRIPT_PATH="$TARGET"
        else
            SCRIPT_PATH="$(dirname "$SCRIPT_PATH")/$TARGET"
        fi
    done
fi
DIR="$(cd "$(dirname "$SCRIPT_PATH")" >/dev/null 2>&1 && pwd)"

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
