# Run Python tests from repo root (Windows).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = "apps"
$env:LOG_LEVEL = "WARNING"
python -m pytest tests @args
