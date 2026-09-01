# Portable test builds

## Linux

Run:

```bash
chmod +x WorkCompanion-Linux-x86_64
./WorkCompanion-Linux-x86_64
```

The executable creates `data/` beside itself when configuration, captures, sessions,
exports, or logs are written. X11 window capture still expects `ffmpeg`, `xwininfo`,
`xdotool`, and `xprop` on the host. Wayland monitor/region support depends on the
desktop compositor's capture permissions.

## Windows

The Windows executable must be built on Windows. Run `packaging/build_windows.ps1`
on a Windows x64 machine, or dispatch `.github/workflows/build-portable.yml` in a
GitHub repository. The result is `releases/WorkCompanion-Windows-x64.exe`.

PyInstaller does not support cross-compiling a Windows executable from Linux, and
this Linux build host does not have Wine installed.
