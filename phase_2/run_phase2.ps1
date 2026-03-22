# Run Phase 2 analysis (pass-through args, e.g. --week 2026-W11)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$check = python -c "import config; k=(config.GROQ_API_KEY or '').strip(); import sys; sys.exit(0 if k else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "GROQ_API_KEY is missing or empty." -ForegroundColor Red
    Write-Host "Edit .env in this folder and set: GROQ_API_KEY=your_key" -ForegroundColor Yellow
    Write-Host "Get a key: https://console.groq.com/keys" -ForegroundColor Yellow
    exit 1
}

python analyze.py @args
