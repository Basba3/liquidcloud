#!/usr/bin/env python3
"""SoundCloud TUI / LiquidCloud Launcher."""

import sys
from pathlib import Path

# Ensure package root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from liquidcloud.app import main

if __name__ == "__main__":
    main()
