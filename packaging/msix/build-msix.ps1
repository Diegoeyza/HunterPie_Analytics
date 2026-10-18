# Pack the Store (MSIX) bundle from the PyInstaller onedir build.
# Requires the Windows SDK (makeappx.exe). Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File packaging\msix\build-msix.ps1 -Version 1.0.0.0
param([string]$Version = "1.0.0.0")

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$app = Join-Path $root "dist\HunterPieAnalytics"
$stage = Join-Path $root "build\msix"
$out = Join-Path $root "dist\HunterPieAnalytics-$Version.msix"

if (-not (Test-Path $app)) { throw "missing $app — run packaging\build-windows.ps1 first" }

if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item "$app\*" $stage -Recurse
Copy-Item (Join-Path $PSScriptRoot "AppxManifest.xml") $stage
Copy-Item (Join-Path $PSScriptRoot "Assets") $stage -Recurse

# Patch only the <Identity ... Version="..."/> attribute — a bare
# `Version="x.y.z.w"` replace would also hit MinVersion/MaxVersionTested.
$manifestPath = Join-Path $stage "AppxManifest.xml"
$content = Get-Content $manifestPath -Raw
$content = $content -replace '(<Identity[^>]*?\bVersion=")\d+\.\d+\.\d+\.\d+(")', "`${1}$Version`${2}"
Set-Content $manifestPath $content -NoNewline

makeappx pack /d $stage /p $out /o

Write-Host "Built: $out"
Write-Host "Note: the Store re-signs on upload; for sideloading, sign with a trusted cert."
