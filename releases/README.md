# Portable test builds

## Linux

Extract `cupi-Linux-x86_64.tar.gz`, enter the extracted folder, and run:

```bash
chmod +x cupi-Linux-x86_64
./cupi-Linux-x86_64
```

The executable creates `data/` beside itself when configuration, captures, sessions,
exports, or logs are written. X11 window capture still expects `ffmpeg`, `xwininfo`,
`xdotool`, and `xprop` on the host. Wayland monitor/region support depends on the
desktop compositor's capture permissions.

## Windows

The Windows executable must be built on Windows. Run `packaging/build_windows.ps1`
on a Windows x64 machine, or dispatch `.github/workflows/build-portable.yml` in a
GitHub repository. The result is `releases/cupi-Windows-x64.zip`.
Extract the archive and launch `cupi-Windows-x64.exe` inside it.

Keep the complete extracted folder, including `_internal/`, `licenses/`,
the notices, dependency manifest and source archive. These builds use shared
libraries that users can replace. Old standalone executables are obsolete.

PyInstaller does not support cross-compiling a Windows executable from Linux, and
this Linux build host does not have Wine installed.

Never include `data/` when distributing binaries: it can contain API keys, captures and private exports. Binaries need the dependency license notices and corresponding distribution obligations described in the project README. Build Linux releases on the oldest supported Linux baseline; a local newer-glibc build is only a test artifact.
