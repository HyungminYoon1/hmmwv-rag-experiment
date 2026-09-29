$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
$listener = Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw 'Port 11435 is already in use. Keep the existing server intact and use a separate reproduction session.' }
Push-Location -LiteralPath $packageRoot
try {
    & (Join-Path $packageRoot 'experiment/start_ollama.ps1')
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $version = Invoke-RestMethod -Uri 'http://127.0.0.1:11435/api/version' -TimeoutSec 2
            Write-Output ('Ollama ready: ' + $version.version)
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) { throw 'Ollama did not become ready; inspect experiment/reports/ollama-stderr.log.' }
} finally {
    Pop-Location
}
