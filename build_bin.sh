#!/usr/bin/env bash
# ==============================================================================
# LiquidCloud Standalone Binary Build Script
# Builds a single portable executable using PyInstaller.
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "💧 Building LiquidCloud Standalone Binary..."

# Use virtualenv python if available
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON="$DIR/.venv/bin/python"
    PIP="$DIR/.venv/bin/pip"
    PYINSTALLER="$DIR/.venv/bin/pyinstaller"
else
    PYTHON="python3"
    PIP="pip3"
    PYINSTALLER="pyinstaller"
fi

# Ensure PyInstaller is installed
if ! command -v "$PYINSTALLER" &> /dev/null && ! "$PYTHON" -m pyinstaller --version &> /dev/null; then
    echo "📦 Installing PyInstaller in virtualenv..."
    "$PIP" install pyinstaller
fi

# Clean previous build artifacts
rm -rf "$DIR/build" "$DIR/dist" "$DIR/*.spec"

echo "⚙️ Packaging application with PyInstaller..."
"$PYTHON" -m PyInstaller \
    --onefile \
    --name liquidcloud \
    --add-data "liquidcloud/styles.tcss:liquidcloud" \
    --hidden-import "liquidcloud" \
    --hidden-import "liquidcloud.api" \
    --hidden-import "liquidcloud.app" \
    --hidden-import "liquidcloud.player" \
    --hidden-import "liquidcloud.queue_manager" \
    --hidden-import "liquidcloud.storage" \
    --hidden-import "liquidcloud.ui" \
    --hidden-import "liquidcloud.ui.modals" \
    --hidden-import "liquidcloud.ui.player_bar" \
    --hidden-import "liquidcloud.ui.sidebar" \
    --hidden-import "liquidcloud.ui.track_table" \
    --clean \
    "$DIR/liquidcloud.py"

echo "✅ Build complete!"
echo "📁 Binary location: $DIR/dist/liquidcloud"
ls -lh "$DIR/dist/liquidcloud"
