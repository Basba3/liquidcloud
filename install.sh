#!/usr/bin/env bash
# ==============================================================================
# LiquidCloud Quick Installer
# Sets up the virtualenv and creates a symlink in ~/.local/bin
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

echo "💧 Installing LiquidCloud..."

# Check requirements
if ! command -v mpv &> /dev/null; then
    echo "⚠️ Warning: 'mpv' is required for playback. Install it with your package manager (e.g. sudo pacman -S mpv / sudo apt install mpv)"
fi

# 1. Setup virtual environment
if [ ! -f "$DIR/.venv/bin/python" ]; then
    echo "📦 Initializing virtual environment..."
    python3 -m venv "$DIR/.venv"
    echo "📦 Installing dependencies (Textual, yt-dlp)..."
    "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
fi

# 2. Create launcher symlink in ~/.local/bin
mkdir -p "$HOME/.local/bin"
ln -sf "$DIR/run.sh" "$HOME/.local/bin/liquidcloud"
chmod +x "$DIR/run.sh"

echo ""
echo "✅ Installation complete!"
echo "🚀 You can now run 'liquidcloud' from anywhere in your terminal!"
