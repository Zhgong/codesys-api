# PowerShell Script to start CODESYS API server with local environment configuration

$EnvFile = ".env.real-codesys.local"

if (Test-Path $EnvFile) {
    Write-Host "Loading environment from $EnvFile..." -ForegroundColor Cyan
    Get-Content $EnvFile | ForEach-Object {
        # Skip comments and empty lines
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        
        # Split by the first '='
        $name, $value = $_ -split '=', 2
        if ($name -and $value) {
            $name = $name.Trim()
            $value = $value.Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
            # Write-Host "Set $name = $value" -ForegroundColor DarkGray
        }
    }
} else {
    Write-Error "$EnvFile not found!"
    exit 1
}

Write-Host "Starting CODESYS API HTTP Server..." -ForegroundColor Green
python .\HTTP_SERVER.py
