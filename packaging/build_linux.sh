#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
python_bin="${PYTHON_BIN:-python3}"
if [[ -z "${PYTHON_BIN:-}" && -x "$repo_dir/.venv/bin/python" ]]; then
  python_bin="$repo_dir/.venv/bin/python"
fi

# Build the tiny native client used for clean, unobscured Hyprland window
# capture. The helper and replaceable Qt libraries live in the release folder.
helper_build_dir="$(mktemp -d)"
trap 'rm -rf "$helper_build_dir"' EXIT
wayland-scanner client-header \
  capture/hyprland-toplevel-export-v1.xml \
  "$helper_build_dir/hyprland-toplevel-export-v1-client-protocol.h"
wayland-scanner private-code \
  capture/hyprland-toplevel-export-v1.xml \
  "$helper_build_dir/hyprland-toplevel-export-v1-client-protocol.c"
cc -O2 -I"$helper_build_dir" -c \
  "$helper_build_dir/hyprland-toplevel-export-v1-client-protocol.c" \
  -o "$helper_build_dir/protocol.o"
c++ -std=c++17 -O2 -I"$helper_build_dir" \
  capture/hyprland_toplevel_capture.cpp \
  "$helper_build_dir/protocol.o" \
  $(pkg-config --cflags --libs wayland-client) \
  -o "$helper_build_dir/awc-hyprland-toplevel-capture"

"$python_bin" -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name cupi-Linux-x86_64 \
  --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module PySide2 \
  --paths "$repo_dir" \
  --specpath "$repo_dir/build/specs" \
  --add-data "$repo_dir/assets:assets" \
  --add-binary "$helper_build_dir/awc-hyprland-toplevel-capture:." \
  packaging/portable_entry.py
"$python_bin" packaging/release_bundle.py dist/cupi-Linux-x86_64
mkdir -p releases
tar -C dist -czf releases/cupi-Linux-x86_64.tar.gz cupi-Linux-x86_64
