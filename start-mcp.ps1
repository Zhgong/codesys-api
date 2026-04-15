# Start MCP_SERVER.py with environment variables loaded from .env.real-codesys.local
param(
    [string]$EnvFile = ".env.real-codesys.local"
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvPath = Join-Path $RepoRoot $EnvFile

if (-not (Test-Path $EnvPath)) {
    Write-Error "Env file not found: $EnvPath"
    exit 1
}

# Load env vars from file (skip comments and blank lines)
Get-Content $EnvPath | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_ -split '=', 2
    [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim())
    Write-Host "  SET $($name.Trim())"
}

Write-Host ""
Write-Host "Starting MCP_SERVER.py ..."
Write-Host ""

Set-Location $RepoRoot
python MCP_SERVER.py
