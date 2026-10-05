"""Exercise byte order for every shared-memory format supported by the helper."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.fixture(scope='module')
def native_color_helper(tmp_path_factory):
    if not sys.platform.startswith('linux') or any(not shutil.which(tool) for tool in ('c++', 'cc', 'wayland-scanner', 'pkg-config')):
        pytest.skip('Native Wayland build tools unavailable')
    flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'wayland-client'], capture_output=True, text=True)
    if flags.returncode:
        pytest.skip('Wayland development files unavailable')
    directory = tmp_path_factory.mktemp('native-colors')
    root = Path(__file__).resolve().parents[1]
    protocol = root / 'capture/hyprland-toplevel-export-v1.xml'
    header = directory / 'hyprland-toplevel-export-v1-client-protocol.h'
    source = directory / 'protocol.c'
    subprocess.run(['wayland-scanner', 'client-header', str(protocol), str(header)], check=True)
    subprocess.run(['wayland-scanner', 'private-code', str(protocol), str(source)], check=True)
    subprocess.run(['cc', '-c', str(source), '-o', str(directory / 'protocol.o')], check=True)
    harness = directory / 'colors.cpp'
    harness.write_text('''#define main capture_main
#include "capture/hyprland_toplevel_capture.cpp"
#undef main
int main(int argc, char** argv) {
    uint32_t formats[] = {WL_SHM_FORMAT_ARGB8888, WL_SHM_FORMAT_XRGB8888,
                         WL_SHM_FORMAT_ABGR8888, WL_SHM_FORMAT_XBGR8888,
                         WL_SHM_FORMAT_RGBA8888, WL_SHM_FORMAT_RGBX8888};
    uint8_t pixels[][4] = {{56,34,12,78},{56,34,12,0},{12,34,56,78},
                          {12,34,56,0},{78,56,34,12},{0,56,34,12}};
    int index = std::atoi(argv[1]);
    FrameState frame;
    frame.format = formats[index]; frame.width = 1; frame.height = 1; frame.stride = 4;
    return output_rgba(frame, pixels[index]) ? 0 : 1;
}
''')
    binary = directory / 'colors'
    subprocess.run(['c++', '-std=c++17', '-I' + str(directory), '-I' + str(root), str(harness), str(directory / 'protocol.o'), *flags.stdout.split(), '-o', str(binary)], check=True)
    return binary


@pytest.mark.parametrize('index', range(6))
def test_native_capture_color_channels(native_color_helper, index):
    result = subprocess.run([str(native_color_helper), str(index)], capture_output=True, check=True)
    assert result.stdout[:4] == b'AWC1'
    assert result.stdout[16:] == bytes((12, 34, 56, 78 if index % 2 == 0 else 255))
