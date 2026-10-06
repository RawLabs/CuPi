$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoDir
python -m pip install pyinstaller -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
python -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name cupi-Windows-x64 `
  --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module PySide2 `
  --paths $RepoDir `
  --specpath build/specs `
  --add-data "$RepoDir\assets;assets" `
  packaging/portable_entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
New-Item -ItemType Directory -Force releases | Out-Null
python packaging/release_bundle.py dist/cupi-Windows-x64
if ($LASTEXITCODE -ne 0) { throw "Release bundle assembly failed" }
Compress-Archive -Path dist/cupi-Windows-x64 -DestinationPath releases/cupi-Windows-x64.zip -Force
