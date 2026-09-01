#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "✨ Starting Screen-Aware AI Work Companion"
echo "=========================================="

missing_modules=()
python3 -c "import PyQt6" 2>/dev/null || missing_modules+=("python-pyqt6")
python3 -c "import numpy" 2>/dev/null || missing_modules+=("python-numpy")
python3 -c "import requests" 2>/dev/null || missing_modules+=("python-requests")

if (( ${#missing_modules[@]} )); then
    echo "Missing runtime dependencies: ${missing_modules[*]}"
    echo "Install them with:"
    echo "  sudo pacman -S --needed ${missing_modules[*]}"
    exit 1
fi

# Run main application
python3 main.py "$@"
