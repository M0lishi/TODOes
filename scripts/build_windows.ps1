$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m pip install -r requirements.txt pyinstaller==6.16.0
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/build_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name TODOes --icon assets/todoes.ico --add-data "assets/todoes.svg;assets" main.py
exit $LASTEXITCODE
