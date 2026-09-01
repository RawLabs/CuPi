$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoDir
python -m pip install --upgrade pyinstaller PyQt6 requests Pillow numpy
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name WorkCompanion-Windows-x64 `
  --paths $RepoDir `
  packaging/portable_entry.py
New-Item -ItemType Directory -Force releases | Out-Null
Copy-Item dist/WorkCompanion-Windows-x64.exe releases/
