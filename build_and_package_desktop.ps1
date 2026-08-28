# =============================================================================
# UHO Hub 2.0 Desktop Build & Packaging Script
# Compiles app.py via PyInstaller (UHOHub.spec) and outputs to Desktop
# =============================================================================
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "UHO Hub 2.0 Desktop Build & Packaging Pipeline" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = Get-Location }
Set-Location $ProjectRoot

$DesktopPath = "C:\Users\louis\Desktop"
if (-not (Test-Path $DesktopPath)) {
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
}

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "Desktop Destination: $DesktopPath" -ForegroundColor Gray

# Step 1: Run PyInstaller
Write-Host "`n[1/4] Baue Standalone EXE mit PyInstaller (UHOHub.spec)..." -ForegroundColor Yellow
Get-Process -Name "UHOHub" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
$PythonCmd = "python"
if (Test-Path "$ProjectRoot\venv\Scripts\python.exe") {
    $PythonCmd = "$ProjectRoot\venv\Scripts\python.exe"
}

& $PythonCmd -m PyInstaller --clean --noconfirm "$ProjectRoot\UHOHub.spec"

$DistExe = "$ProjectRoot\dist\UHOHub.exe"
if (-not (Test-Path $DistExe)) {
    Write-Error "Build fehlgeschlagen: $DistExe wurde nicht gefunden!"
    exit 1
}

$ExeSizeMB = [math]::Round(((Get-Item $DistExe).Length / 1MB), 2)
Write-Host "Standalone Binary erfolgreich erstellt ($ExeSizeMB MB): $DistExe" -ForegroundColor Green

# Step 2: Copy to Desktop
Write-Host "`n[2/4] Kopiere UHOHub.exe nach $DesktopPath..." -ForegroundColor Yellow
$DesktopExe = Join-Path $DesktopPath "UHOHub.exe"
Copy-Item -Path $DistExe -Destination $DesktopExe -Force
Write-Host "$DesktopExe erfolgreich bereitgestellt!" -ForegroundColor Green

# Step 3: Create Zip Release Package
Write-Host "`n[3/4] Erstelle UHOHub.zip Release-Archiv..." -ForegroundColor Yellow
$TempReleaseDir = Join-Path $ProjectRoot "build\uho_hub_release"
if (Test-Path $TempReleaseDir) { Remove-Item -Path $TempReleaseDir -Recurse -Force }
New-Item -ItemType Directory -Path $TempReleaseDir -Force | Out-Null

Copy-Item -Path $DistExe -Destination "$TempReleaseDir\UHOHub.exe" -Force
if (Test-Path "$ProjectRoot\beatmaps_analyzed.db") {
    Copy-Item -Path "$ProjectRoot\beatmaps_analyzed.db" -Destination "$TempReleaseDir\beatmaps_analyzed.db" -Force
}
if (Test-Path "$ProjectRoot\compact_ranked_maps.json") {
    Copy-Item -Path "$ProjectRoot\compact_ranked_maps.json" -Destination "$TempReleaseDir\compact_ranked_maps.json" -Force
}
if (Test-Path "$ProjectRoot\official_tournament_pools.json") {
    Copy-Item -Path "$ProjectRoot\official_tournament_pools.json" -Destination "$TempReleaseDir\official_tournament_pools.json" -Force
}

$DesktopZip = Join-Path $DesktopPath "UHOHub.zip"
if (Test-Path $DesktopZip) { Remove-Item -Path $DesktopZip -Force }

Compress-Archive -Path "$TempReleaseDir\*" -DestinationPath $DesktopZip -Force
$ZipSizeMB = [math]::Round(((Get-Item $DesktopZip).Length / 1MB), 2)
Write-Host "Release-Archiv erstellt ($ZipSizeMB MB): $DesktopZip" -ForegroundColor Green

# Step 4: Verification Summary
Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "BUILD AND PACKAGING ERFOLGREICH ABGESCHLOSSEN!" -ForegroundColor Green
Write-Host "Ausfuehrbare Datei: $DesktopExe" -ForegroundColor White
Write-Host "Release-Archiv:     $DesktopZip" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
