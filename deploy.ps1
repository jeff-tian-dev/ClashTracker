# deploy.ps1 — Push project files to Oracle Cloud VM and run setup
#
# Usage:  .\deploy.ps1
#
# Prerequisites:
#   - .env.local exists in project root with ORACLE_SERVER_IP and ORACLE_SSH_KEY_PATH
#   - SSH key file exists at the path specified in ORACLE_SSH_KEY_PATH
#   - Oracle Cloud security list allows inbound TCP on port 8000
#

$ErrorActionPreference = "Stop"

# ---- Load config from .env.local ----
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ProjectRoot ".env.local"

if (-not (Test-Path $EnvFile)) {
    Write-Error ".env.local not found at $EnvFile"
    exit 1
}

$envVars = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.+)$') {
        $envVars[$Matches[1]] = $Matches[2].Trim()
    }
}

$ServerIP  = $envVars["ORACLE_SERVER_IP"]
$KeyPath   = $envVars["ORACLE_SSH_KEY_PATH"]

# Resolve relative key path
if ($KeyPath -match '^\.[\\/]') {
    $KeyPath = Join-Path $ProjectRoot ($KeyPath -replace '^\.[\\/]', '')
}

if (-not $ServerIP) { Write-Error "ORACLE_SERVER_IP not set in .env.local"; exit 1 }
if (-not (Test-Path $KeyPath)) { Write-Error "SSH key not found at $KeyPath"; exit 1 }

$User = "ubuntu"
$RemoteDir = "/home/ubuntu/clash-tracker"
$SSHOpts = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=no")

Write-Host "=== Deploying to $User@$ServerIP ===" -ForegroundColor Cyan

# ---- 1. Create remote directory ----
Write-Host "[1/4] Creating remote directory..."
ssh @SSHOpts "$User@$ServerIP" "mkdir -p $RemoteDir"

# ---- 2. Copy only backend (api, ingestion, shared — no web, no static SPA) ----
Write-Host "[2/4] Copying files to VM..."

ssh @SSHOpts "$User@$ServerIP" "mkdir -p $RemoteDir/apps"

# Drop any legacy static/ tree from older deploys (UI is GitHub Pages only).
ssh @SSHOpts "$User@$ServerIP" "rm -rf $RemoteDir/static"

# Drop legacy apps/web (node_modules); backend-only deploy — UI is GitHub Pages.
ssh @SSHOpts "$User@$ServerIP" "rm -rf $RemoteDir/apps/web"

# Fresh tree for Python apps: Windows OpenSSH recursive scp can leave stale files (e.g. new modules missing).
ssh @SSHOpts "$User@$ServerIP" "rm -rf $RemoteDir/apps/api $RemoteDir/apps/ingestion $RemoteDir/apps/shared"
# Remove mistaken top-level copies from older deploy.ps1 (scp -r apps/api to RemoteDir/ created api/, not apps/api).
ssh @SSHOpts "$User@$ServerIP" "rm -rf $RemoteDir/api $RemoteDir/ingestion $RemoteDir/shared"

$FilesToCopy = @(
    "apps/api",
    "apps/ingestion",
    "apps/shared",
    "deploy",
    ".env.local"
)

foreach ($item in $FilesToCopy) {
    $localPath = Join-Path $ProjectRoot $item
    if (Test-Path $localPath -PathType Container) {
        Write-Host "  Syncing directory: $item"
        # scp -r apps/api host:remote/ puts folder as remote/api — target must be remote/apps/ to get remote/apps/api.
        $parentRel = Split-Path -Parent $item
        if ([string]::IsNullOrEmpty($parentRel)) {
            $remoteParent = $RemoteDir
        } else {
            $remoteParent = "$RemoteDir/$($parentRel.Replace('\', '/'))"
        }
        ssh @SSHOpts "$User@$ServerIP" "mkdir -p $remoteParent"
        scp @SSHOpts -r $localPath "${User}@${ServerIP}:${remoteParent}/"
    } else {
        Write-Host "  Copying file: $item"
        scp @SSHOpts $localPath "${User}@${ServerIP}:${RemoteDir}/$item"
    }
}

# ---- 3. Run setup script on VM ----
Write-Host "[3/4] Running setup on VM..."
ssh @SSHOpts "$User@$ServerIP" "bash $RemoteDir/deploy/setup-vm.sh"

# ---- 4. Verify ----
Write-Host "[4/4] Verifying API health..."
Start-Sleep -Seconds 3
try {
    $health = Invoke-RestMethod -Uri "http://${ServerIP}:8000/health" -TimeoutSec 10
    Write-Host "API is up: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "API health check failed (may need a moment to start). Try: http://${ServerIP}:8000/health" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Deployment complete ===" -ForegroundColor Cyan
Write-Host "  API:       http://${ServerIP}:8000" -ForegroundColor White
Write-Host "  Health:    http://${ServerIP}:8000/health" -ForegroundColor White
Write-Host "  Ingestion: ssh -i $KeyPath $User@$ServerIP 'sudo systemctl status clash-tracker-ingestion.timer'" -ForegroundColor White
Write-Host "  Logs:      ssh -i $KeyPath $User@$ServerIP 'journalctl -u clash-tracker-api -f'" -ForegroundColor White
