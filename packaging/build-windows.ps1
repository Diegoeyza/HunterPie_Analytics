# Build the packaged Windows desktop app (onedir). Run from the repo root.
#   powershell -ExecutionPolicy Bypass -File packaging\build-windows.ps1
$ErrorActionPreference = "Stop"

Write-Host "== Dashboard (static export) =="
$env:NEXT_OUTPUT = "export"
npm ci --prefix dashboard
npm run build --prefix dashboard

Write-Host "== Python deps =="
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt -r packaging/requirements-pack.txt

Write-Host "== PyInstaller =="
python -m PyInstaller --noconfirm --clean packaging/HunterPieAnalytics.spec

Write-Host ""
Write-Host "Built: dist/HunterPieAnalytics/HunterPieAnalytics.exe"
