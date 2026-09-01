#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

# Build the tiny native client used for clean, unobscured Hyprland window
# capture. It is bundled into the one-file release and extracted by PyInstaller
# next to the Python entry point at runtime.
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

python3 -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name WorkCompanion-Linux-x86_64 \
  --paths "$repo_dir" \
  --add-binary "$helper_build_dir/awc-hyprland-toplevel-capture:." \
  packaging/portable_entry.py
mkdir -p releases
cp "dist/WorkCompanion-Linux-x86_64" releases/
