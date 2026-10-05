#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "✨ Starting CᵘPⁱ"
echo "=========================================="

PYTHON_BIN="python3"
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
fi

missing_modules=()
"$PYTHON_BIN" -c "import PySide6" 2>/dev/null || missing_modules+=("pyside6")
"$PYTHON_BIN" -c "import numpy" 2>/dev/null || missing_modules+=("python-numpy")
"$PYTHON_BIN" -c "import requests" 2>/dev/null || missing_modules+=("python-requests")

"$PYTHON_BIN" -c "import docx" 2>/dev/null || missing_modules+=("python-docx")

if (( ${#missing_modules[@]} )); then
    echo "Missing runtime dependencies: ${missing_modules[*]}"
    echo "Install them with:"
    echo "  $PYTHON_BIN -m pip install -r requirements.txt"
    exit 1
fi

# Run main application
"$PYTHON_BIN" main.py "$@"
