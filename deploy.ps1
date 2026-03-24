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
$SSHOpts = @(
    "-i", $KeyPath,
    "-o", "StrictHostKeyChecking=no",
    "-o", "ConnectTimeout=30",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=3"
)

Write-Host "=== Deploying to $User@$ServerIP ===" -ForegroundColor Cyan

# ---- 1. Create remote directory ----
Write-Host "[1/5] Creating remote directory..."
ssh @SSHOpts "$User@$ServerIP" "mkdir -p $RemoteDir"

# ---- 2. Copy only backend (api, ingestion, shared — no web, no static SPA) ----
# One .tar.gz + single scp is faster and more reliable than recursive scp (fewer round trips, compression).
Write-Host "[2/5] Copying files to VM..."

# One SSH session for remote prep (fewer round trips than separate calls).
$remotePrep = "mkdir -p $RemoteDir/apps && rm -rf $RemoteDir/static $RemoteDir/apps/web $RemoteDir/apps/api $RemoteDir/apps/ingestion $RemoteDir/apps/shared $RemoteDir/api $RemoteDir/ingestion $RemoteDir/shared"
ssh @SSHOpts "$User@$ServerIP" $remotePrep

$RemoteTar = "/tmp/clash-tracker-deploy.tar.gz"
$LocalTar = Join-Path ([System.IO.Path]::GetTempPath()) ("clash-tracker-deploy-" + [Guid]::NewGuid().ToString("n") + ".tar.gz")

try {
    Write-Host "  Building archive (apps/api, apps/ingestion, apps/shared, deploy, .env.local)..."
    $tarArgs = @(
        "-czf", $LocalTar,
        "-C", $ProjectRoot,
        "apps/api", "apps/ingestion", "apps/shared", "deploy", ".env.local"
    )
    & tar @tarArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "tar failed (exit $LASTEXITCODE). Is GNU/BSD tar available? (Windows 10+ includes tar.exe.)"
    }

    Write-Host "  Uploading bundle..."
    scp @SSHOpts $LocalTar "${User}@${ServerIP}:${RemoteTar}"

    Write-Host "  Extracting on server..."
    $extractCmd = "cd $RemoteDir && tar -xzf $RemoteTar && rm -f $RemoteTar"
    ssh @SSHOpts "$User@$ServerIP" $extractCmd
}
finally {
    if (Test-Path $LocalTar) {
        Remove-Item -Force $LocalTar -ErrorAction SilentlyContinue
    }
}

# ---- 3. Run setup script on VM ----
Write-Host "[3/5] Running setup on VM..."
ssh @SSHOpts "$User@$ServerIP" "bash $RemoteDir/deploy/setup-vm.sh"

# ---- 4. Restart API so uvicorn loads new code (enable --now does not restart a running unit) ----
Write-Host "[4/5] Restarting clash-tracker-api..."
ssh @SSHOpts "$User@$ServerIP" "sudo systemctl restart clash-tracker-api"

# ---- 5. Verify ----
Write-Host "[5/5] Verifying API health..."
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
