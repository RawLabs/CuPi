#!/usr/bin/env bash
# Build the clean Hyprland window-capture helper for source-checkout testing.
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT

wayland-scanner client-header \
  "$repo_dir/capture/hyprland-toplevel-export-v1.xml" \
  "$build_dir/hyprland-toplevel-export-v1-client-protocol.h"
wayland-scanner private-code \
  "$repo_dir/capture/hyprland-toplevel-export-v1.xml" \
  "$build_dir/hyprland-toplevel-export-v1-client-protocol.c"
cc -O2 -I"$build_dir" -c "$build_dir/hyprland-toplevel-export-v1-client-protocol.c" -o "$build_dir/protocol.o"
c++ -std=c++17 -O2 -I"$build_dir" "$repo_dir/capture/hyprland_toplevel_capture.cpp" "$build_dir/protocol.o" \
  $(pkg-config --cflags --libs wayland-client) -o "$repo_dir/capture/awc-hyprland-toplevel-capture"
chmod +x "$repo_dir/capture/awc-hyprland-toplevel-capture"
echo "Built capture/awc-hyprland-toplevel-capture for source-checkout testing."
